"""tests/unit/e_taxis/transpile/adapters/capture: the fake model keeps every body and refuses with a final 400 — or,
answering, speaks one turn in the protocol of the route: the reply's tool once, then a closing text."""

from typing import TYPE_CHECKING

import anyio
import msgspec
import pytest

from e_taxis.transpile.adapters.capture import HttpCapture

if TYPE_CHECKING:
    from collections.abc import Mapping


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


def _post(path: str, request: Mapping[str, object]) -> bytes:
    body = msgspec.json.encode(request)
    return f"POST {path} HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body


@pytest.mark.parametrize(
    ("path", "tools", "stream", "called", "spoken"),
    [
        ("/v1/messages", [{"name": "Bash"}], True, b'"stop_reason":"tool_use"', b'"text":"ghost"'),
        ("/v1/messages", [{"name": "Bash"}], False, b'"name":"Bash","input":{"command":"true"}', b'"end_turn"'),
        ("/v1/chat/completions", [{"function": {"name": "Bash"}}], True, b'"tool_calls"', b"data: [DONE]"),
        (
            "/v1/chat/completions",
            [{"function": {"name": "Bash"}}],
            False,
            b'"finish_reason":"tool_calls"',
            b'"content":"ghost"',
        ),
    ],
    ids=["anthropic-stream", "anthropic", "openai-stream", "openai"],
)
async def test_capture_answers_the_tool_once_then_text(
    path: str, tools: list[object], stream: bool, called: bytes, spoken: bytes
) -> None:
    capture = HttpCapture()
    capture.answer({"tool": "Bash", "input": {"command": "true"}})
    request = {"model": "m", "stream": stream, "tools": tools}
    async with capture.serve():
        first = await _send(capture, _post(path, request))
        second = await _send(capture, _post(path, request))
    assert first.startswith(b"HTTP/1.1 200")
    assert called in first
    assert spoken in second
    assert b"tool_calls" not in second.replace(b"finish_reason", b"")


async def test_capture_answers_text_where_the_tool_is_not_offered_and_refuses_other_routes() -> None:
    capture = HttpCapture()
    capture.answer({"tool": "Bash"})
    async with capture.serve():
        titled = await _send(capture, _post("/v1/chat/completions", {"model": "m", "stream": True}))
        counted = await _send(capture, _post("/v1/messages/count_tokens", {"model": "m"}))
        capture.answer(None)
        refused = await _send(capture, _post("/v1/messages", {"model": "m"}))
    assert b'"content":"ghost"' in titled
    assert counted.startswith(b"HTTP/1.1 400")
    assert refused.startswith(b"HTTP/1.1 400")


async def test_capture_clear_lets_the_tool_be_called_again() -> None:
    capture = HttpCapture()
    capture.answer({"tool": "Bash"})
    request = {"model": "m", "tools": [{"name": "Bash"}]}
    async with capture.serve():
        await _send(capture, _post("/v1/messages", request))
        capture.clear()
        again = await _send(capture, _post("/v1/messages", request))
    assert b'"tool_use"' in again
