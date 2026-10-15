"""adapters.primitives.binary: a release binary — downloaded, its sha256 checked, extracted, placed executable.

No sha256, no install: an unchecked binary on PATH is the one thing this primitive refuses outright. The
download lands in a scratch dir and is checked before anything reaches `path`; the placed file is the one
recorded effect, so a failing `then` still leaves undo able to take it back."""

import hashlib
import shlex
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from e_taxis.adapters.disk import read_file, remove_file, write_file
from e_taxis.models.error import DigestError, RecipeError, RunnerError
from e_taxis.models.journal import JournalFile
from e_taxis.models.primitive import PrimitiveStep
from e_taxis.models.recipe import RecipeBinary, RecipeBinaryPath

if TYPE_CHECKING:
    from e_taxis.adapters.ports import DownloaderPort, RunnerPort
    from e_taxis.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.models.primitive import PrimitiveContext

##### DEFAULTS #####
EXECUTABLE: int = 0o755


##### TYPES #####
class BinaryPrimitive:
    """Satisfies PrimitivePort; `temp` is where downloads are staged (None: the system's temp dir)."""

    __slots__ = ("_downloader", "_runner", "_temp")

    def __init__(self, downloader: DownloaderPort, runner: RunnerPort, temp: Path | None) -> None:
        self._downloader = downloader
        self._runner = runner
        self._temp = None if temp is None else str(temp)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _install_digest(blob: Path) -> str:
        with blob.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    @staticmethod
    def _install_member(blob: Path, member: str) -> bytes:
        """The member's bytes, matched by name or as the last segment of a nested path; read, never extracted to disk."""
        try:
            with tarfile.open(blob, "r:gz") as tar:
                found = next(
                    (
                        tar.extractfile(item)
                        for item in tar.getmembers()
                        if item.isfile() and (item.name == member or item.name.endswith(f"/{member}"))
                    ),
                    None,
                )
                match found:
                    case None:
                        msg = f"no member {member!r} in the archive"
                        raise RecipeError(msg)
                    case handle:
                        return handle.read()
        except tarfile.TarError as exc:
            msg = f"not a tar.gz: {exc}"
            raise RecipeError(msg) from exc

    async def _install_fetch(self, entry: CatalogEntry, args: RecipeBinary) -> bytes:
        """The checked payload: downloaded to scratch, sha256 compared, the member read out when one is named."""
        async with anyio.TemporaryDirectory(dir=self._temp) as scratch:
            blob = Path(scratch) / "download"
            await self._downloader.fetch(args.url, blob)
            digest = await anyio.to_thread.run_sync(self._install_digest, blob)
            match digest == (args.sha256 or "").lower():
                case False:
                    msg = f"{entry.id}: sha256 {digest} does not match the pinned {args.sha256}"
                    raise DigestError(msg)
                case _:
                    pass
            match args.member:
                case None:
                    return await anyio.Path(blob).read_bytes()
                case member:
                    return await anyio.to_thread.run_sync(self._install_member, blob, member)

    async def _install_then(self, commands: tuple[str, ...], placed: tuple[JournalFile, ...]) -> None:
        try:
            _ = [await self._runner.run(tuple(shlex.split(command))) for command in commands]
        except RunnerError as exc:
            raise RunnerError(exc.message, effects=placed) from exc

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        args = recipe.args(RecipeBinary)
        match args.sha256:
            case None:
                msg = f"{entry.id}: no sha256 for {args.url} — an unchecked binary is never placed"
                raise DigestError(msg)
            case _:
                pass
        data = await self._install_fetch(entry, args)
        path = ctx.expand(args.path)
        prior = await read_file(path)
        before, mode = prior or (None, None)
        match prior == (data, EXECUTABLE):
            case True:
                placed: tuple[JournalFile, ...] = ()
            case _:
                await write_file(path, data, EXECUTABLE)
                placed = (JournalFile(path=str(path), before=before, mode=mode),)
        await self._install_then(args.then, placed)
        return PrimitiveStep(effects=placed, detail=f"placed {path}")

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        path = ctx.expand(recipe.args(RecipeBinaryPath).path)
        match await read_file(path):
            case None:
                return PrimitiveStep(detail="absent")
            case found:
                data, mode = found
                await remove_file(path)
                return PrimitiveStep(
                    effects=(JournalFile(path=str(path), before=data, mode=mode),), detail=f"removed {path}"
                )
