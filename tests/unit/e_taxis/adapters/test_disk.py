"""tests/unit/e_taxis/adapters/disk: whole-file reads with their mode, atomic writes, idempotent removal."""

from typing import TYPE_CHECKING

from e_taxis.adapters.disk import mode_file, read_file, remove_file, write_file

if TYPE_CHECKING:
    from pathlib import Path


async def test_disk_read_absent_is_none(tmp_path: Path) -> None:
    assert (await read_file(tmp_path / "nope"), await mode_file(tmp_path / "nope")) == (None, None)


async def test_disk_write_creates_parents_and_sets_the_mode(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "bin"
    await write_file(path, b"x", 0o755)
    assert await read_file(path) == (b"x", 0o755)
    assert [item.name for item in path.parent.iterdir()] == ["bin"]


async def test_disk_write_over_a_file_keeps_its_mode(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b"old")
    path.chmod(0o600)
    await write_file(path, b"new")
    assert await read_file(path) == (b"new", 0o600)


async def test_disk_remove_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"x")
    await remove_file(path)
    await remove_file(path)
    assert not path.exists()
