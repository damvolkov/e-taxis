"""tests/unit/e_taxis/transpile/adapters/capture: the fake model keeps every body and refuses with a final 400."""

import anyio
import pytest

from e_taxis.transpile.adapters.capture import HttpCapture


async def _send(capture: HttpCapture, raw: bytes) -> bytes:
    async with await anyio.connect_tcp("127.0.0.1", capture.port) as stream:
        await stream.send(raw)
        return b"".join([chunk async for chunk in stream])


@pytest.mark.parametrize(
    ("raw", "body"),
    [
        (b"POST /v1/messages HTTP/1.1\r\nContent-Length: 5\r\n\r\nhello", b"hello"),
        (b"POST /v1 HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n", b"abcde"),
        (b"GET / HTTP/1.1\r\nHost: x\r\n\r\n", b""),
    ],
    ids=["length", "chunked", "bare"],
)
async def test_capture_keeps_the_body_and_refuses(raw: bytes, body: bytes) -> None:
    capture = HttpCapture()
    async with capture.serve():
        answer = await _send(capture, raw)
    assert answer.startswith(b"HTTP/1.1 400")
    assert capture.bodies() == (body,)
    assert capture.url == f"http://127.0.0.1:{capture.port}"


async def test_capture_a_dropped_connection_is_ignored_and_clear_forgets() -> None:
    capture = HttpCapture()
    async with capture.serve():
        async with await anyio.connect_tcp("127.0.0.1", capture.port) as stream:
            await stream.send(b"POST / HTTP/1.1\r\n")
        await _send(capture, b"POST / HTTP/1.1\r\nContent-Length: 1\r\n\r\nx")
        await anyio.sleep(0.05)
    assert capture.bodies() == (b"x",)
    capture.clear()
    assert capture.bodies() == ()
