"""tests/unit/e_taxis/adapters: a loopback HTTP server over a temp dir — the real downloader never leaves the machine."""

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — the stdlib's own signature
        return


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """(base url, root): files under root are served on 127.0.0.1, a directory without its slash redirects."""
    root = tmp_path / "served"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", root
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
