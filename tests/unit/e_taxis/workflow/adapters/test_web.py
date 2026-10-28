"""tests/unit/e_taxis/workflow/adapters/web: wreq against a loopback server — a page's text, a multipart post."""

import socket

import pytest

from e_taxis.workflow.adapters.web import WreqWeb
from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.ports import WebPort


async def test_web_satisfies_the_port() -> None:
    assert isinstance(WreqWeb(), WebPort)


async def test_web_get_answers_the_text(pages) -> None:
    pages.pages["/post"] = "<p>Señal</p>".encode()
    assert await WreqWeb().get(f"http://127.0.0.1:{pages.server_address[1]}/post") == "<p>Señal</p>"


async def test_web_get_status_error(pages) -> None:
    with pytest.raises(SweepError, match=r"/missing: .*404"):
        await WreqWeb().get(f"http://127.0.0.1:{pages.server_address[1]}/missing")


async def test_web_get_connection_error() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(SweepError, match=f"127.0.0.1:{port}"):
        await WreqWeb(timeout=2).get(f"http://127.0.0.1:{port}/x")


async def test_web_post_sends_the_multipart(pages) -> None:
    url = f"http://127.0.0.1:{pages.server_address[1]}/hook"
    await WreqWeb().post(url, fields={"payload_json": '{"content":"hi"}'}, files={"files[0]": ("r.md", b"# R")})
    kind, body = pages.posted[0]
    assert kind.startswith("multipart/form-data; boundary=")
    assert (b'name="payload_json"' in body, b'{"content":"hi"}' in body) == (True, True)
    assert (b'filename="r.md"' in body, b"# R" in body) == (True, True)


async def test_web_post_status_error(pages) -> None:
    with pytest.raises(SweepError, match="400"):
        await WreqWeb().post(f"http://127.0.0.1:{pages.server_address[1]}/other", fields={}, files={})
