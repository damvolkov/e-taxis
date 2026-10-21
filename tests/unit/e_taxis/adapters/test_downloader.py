"""tests/unit/e_taxis/adapters/downloader: wreq against a loopback server — body streamed to disk, redirects followed."""

import socket
from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.downloader import WreqDownloader
from e_taxis.harness.models.error import DownloadError
from e_taxis.harness.models.ports import DownloaderPort

if TYPE_CHECKING:
    from pathlib import Path


async def test_downloader_satisfies_the_port() -> None:
    assert isinstance(WreqDownloader(timeout=5), DownloaderPort)


async def test_downloader_fetch_streams_the_body(served: tuple[str, Path], tmp_path: Path) -> None:
    base, root = served
    (root / "blob").write_bytes(b"\x00" * 100_000)
    await WreqDownloader(timeout=5).fetch(f"{base}/blob", tmp_path / "out")
    assert (tmp_path / "out").read_bytes() == b"\x00" * 100_000


async def test_downloader_fetch_follows_redirects(served: tuple[str, Path], tmp_path: Path) -> None:
    base, root = served
    (root / "dir").mkdir()
    (root / "dir" / "index.html").write_bytes(b"landed")
    await WreqDownloader(timeout=5).fetch(f"{base}/dir", tmp_path / "out")
    assert (tmp_path / "out").read_bytes() == b"landed"


async def test_downloader_fetch_status_error(served: tuple[str, Path], tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="404"):
        await WreqDownloader(timeout=5).fetch(f"{served[0]}/missing", tmp_path / "out")


async def test_downloader_fetch_connection_error(tmp_path: Path) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(DownloadError, match=f"127.0.0.1:{port}"):
        await WreqDownloader(timeout=5).fetch(f"http://127.0.0.1:{port}/x", tmp_path / "out")
