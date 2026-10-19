"""adapters.disk: the file operations every writing primitive and the undo share — read with mode, atomic write, removal.

A write is staged beside its target and renamed over it, so a crash leaves the old file or the new one,
never half of either; the stage is cleaned up whatever happens."""

import secrets
from contextlib import suppress
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from pathlib import Path


##### UTILITIES #####
async def mode_file(path: Path) -> int | None:
    """The permission bits of `path`, or None where nothing is there."""
    try:
        return (await anyio.Path(path).stat()).st_mode & 0o7777
    except FileNotFoundError:
        return None


async def read_file(path: Path) -> tuple[bytes, int] | None:
    """The bytes and permission bits of `path`, or None where nothing is there."""
    try:
        data = await anyio.Path(path).read_bytes()
    except FileNotFoundError:
        return None
    return (data, await mode_file(path) or 0)


async def write_file(path: Path, data: bytes, mode: int | None = None) -> None:
    """`data` lands whole at `path`, parents created; `mode` defaults to the replaced file's own."""
    target = anyio.Path(path)
    await target.parent.mkdir(parents=True, exist_ok=True)
    kept = mode if mode is not None else await mode_file(path)
    staged = target.with_name(f".{target.name}.taxis-{secrets.token_hex(4)}")
    try:
        await staged.write_bytes(data)
        match kept:
            case None:
                pass
            case bits:
                await staged.chmod(bits)
        await staged.replace(target)
    finally:
        await staged.unlink(missing_ok=True)


async def remove_file(path: Path) -> None:
    """Nothing at `path` afterwards; already nothing is fine."""
    await anyio.Path(path).unlink(missing_ok=True)


async def missing_dirs(path: Path) -> int:
    """How many parents of `path` do not exist yet: the innermost ones, since a parent implies its own."""
    return sum([not await anyio.Path(parent).exists() for parent in path.parents])


async def remove_dirs(path: Path, levels: int) -> None:
    """The `levels` innermost parents of `path` removed, innermost first, stopping at the first one not empty."""
    with suppress(OSError):
        _ = [await anyio.Path(parent).rmdir() for parent in path.parents[:levels]]
