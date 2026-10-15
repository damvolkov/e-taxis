"""tests/unit/e_taxis/adapters/primitives/binary: download, check, extract, place +x, then — and the way back."""

import hashlib
import io
import tarfile
from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.ports import PrimitivePort
from e_taxis.models.error import DigestError, DownloadError, RecipeError, RunnerError
from e_taxis.models.journal import JournalFile
from e_taxis.models.primitive import PrimitiveStep

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.adapters.primitives.binary import BinaryPrimitive

URL = "https://example.invalid/tool"


def _tar(name: str, data: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def test_binary_satisfies_the_port(binary: BinaryPrimitive) -> None:
    assert isinstance(binary, PrimitivePort)


async def test_binary_install_places_an_executable(binary, entry, ctx, downloader, home: Path) -> None:
    downloader.blobs[URL] = b"tool"
    part = entry("binary", {"url": URL, "sha256": _sha(b"tool"), "path": "~/.local/bin/tool"})
    step = await binary.install(part, part.recipe(ctx.target), ctx)
    placed = home / ".local/bin/tool"
    assert (placed.read_bytes(), placed.stat().st_mode & 0o777) == (b"tool", 0o755)
    assert step == PrimitiveStep(effects=(JournalFile(path=str(placed), before=None),), detail=f"placed {placed}")


@pytest.mark.parametrize("name", ["bd", "beads_1.3.1/bd"], ids=["top", "nested"])
async def test_binary_install_extracts_the_member(binary, entry, ctx, downloader, home: Path, name: str) -> None:
    archive = _tar(name, b"bd-binary")
    downloader.blobs[URL] = archive
    part = entry("binary", {"url": URL, "sha256": _sha(archive), "member": "bd", "path": "~/bin/bd"})
    await binary.install(part, part.recipe(ctx.target), ctx)
    assert (home / "bin/bd").read_bytes() == b"bd-binary"


@pytest.mark.parametrize(
    ("blob", "match"), [(_tar("other", b"x"), "no member 'bd'"), (b"plain", "not a tar.gz")], ids=["absent", "not-tar"]
)
async def test_binary_install_member_refused(binary, entry, ctx, downloader, blob: bytes, match: str) -> None:
    downloader.blobs[URL] = blob
    part = entry("binary", {"url": URL, "sha256": _sha(blob), "member": "bd", "path": "~/bin/bd"})
    with pytest.raises(RecipeError, match=match):
        await binary.install(part, part.recipe(ctx.target), ctx)


@pytest.mark.parametrize(
    ("sha", "match"), [(None, "no sha256"), ("0" * 64, "does not match")], ids=["missing", "mismatch"]
)
async def test_binary_install_digest_refused(binary, entry, ctx, downloader, home: Path, sha, match: str) -> None:
    downloader.blobs[URL] = b"tool"
    part = entry("binary", {"url": URL, "sha256": sha, "path": "~/bin/tool"})
    with pytest.raises(DigestError, match=match):
        await binary.install(part, part.recipe(ctx.target), ctx)
    assert not (home / "bin/tool").exists()


async def test_binary_install_download_failure(binary, entry, ctx) -> None:
    part = entry("binary", {"url": URL, "sha256": "0" * 64, "path": "~/bin/tool"})
    with pytest.raises(DownloadError, match="404"):
        await binary.install(part, part.recipe(ctx.target), ctx)


async def test_binary_install_runs_then_after_placing(binary, entry, ctx, downloader, runner) -> None:
    downloader.blobs[URL] = b"tool"
    with_ = {"url": URL, "sha256": _sha(b"tool"), "path": "~/bin/bd", "then": ["bd init --quiet", "bd metrics off"]}
    part = entry("binary", with_)
    await binary.install(part, part.recipe(ctx.target), ctx)
    assert runner.calls == [("bd", "init", "--quiet"), ("bd", "metrics", "off")]


async def test_binary_install_failing_then_keeps_the_placed_file_for_undo(
    binary, entry, ctx, downloader, runner, home: Path
) -> None:
    downloader.blobs[URL] = b"tool"
    runner.failing.add(("bd", "init"))
    part = entry("binary", {"url": URL, "sha256": _sha(b"tool"), "path": "~/bin/bd", "then": ["bd init"]})
    with pytest.raises(RunnerError) as failure:
        await binary.install(part, part.recipe(ctx.target), ctx)
    assert failure.value.effects == (JournalFile(path=str(home / "bin/bd"), before=None),)


async def test_binary_install_unchanged_writes_nothing(binary, entry, ctx, downloader, home: Path) -> None:
    downloader.blobs[URL] = b"tool"
    (home / "bin").mkdir()
    (home / "bin/tool").write_bytes(b"tool")
    (home / "bin/tool").chmod(0o755)
    part = entry("binary", {"url": URL, "sha256": _sha(b"tool"), "path": "~/bin/tool"})
    assert (await binary.install(part, part.recipe(ctx.target), ctx)).effects == ()


async def test_binary_undo_of_an_install_restores_the_prior_file(
    binary, entry, ctx, downloader, undo, home: Path
) -> None:
    downloader.blobs[URL] = b"new"
    (home / "bin").mkdir()
    (home / "bin/tool").write_bytes(b"old")
    (home / "bin/tool").chmod(0o700)
    part = entry("binary", {"url": URL, "sha256": _sha(b"new"), "path": "~/bin/tool"})
    await undo(*(await binary.install(part, part.recipe(ctx.target), ctx)).effects)
    assert ((home / "bin/tool").read_bytes(), (home / "bin/tool").stat().st_mode & 0o777) == (b"old", 0o700)


async def test_binary_uninstall_and_its_undo(binary, entry, ctx, undo, home: Path) -> None:
    (home / "bin").mkdir()
    (home / "bin/tool").write_bytes(b"old")
    part = entry("binary", {"url": URL, "path": "~/bin/tool"}, uninstall={"path": "~/bin/tool"})
    step = await binary.uninstall(part, part.uninstall, ctx)
    assert not (home / "bin/tool").exists()
    await undo(*step.effects)
    assert (home / "bin/tool").read_bytes() == b"old"


async def test_binary_uninstall_absent_changes_nothing(binary, entry, ctx) -> None:
    part = entry("binary", {"url": URL, "path": "~/bin/tool"}, uninstall={"path": "~/bin/tool"})
    assert await binary.uninstall(part, part.uninstall, ctx) == PrimitiveStep(detail="absent")


async def test_binary_undo_of_a_fresh_install_removes_it(binary, entry, ctx, downloader, undo, home: Path) -> None:
    downloader.blobs[URL] = b"tool"
    part = entry("binary", {"url": URL, "sha256": _sha(b"tool"), "path": "~/bin/tool"})
    await undo(*(await binary.install(part, part.recipe(ctx.target), ctx)).effects)
    assert not (home / "bin/tool").exists()
