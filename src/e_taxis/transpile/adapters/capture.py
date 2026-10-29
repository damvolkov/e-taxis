"""adapters.capture: a fake model endpoint that keeps what a harness sent it — the eye of a phantom.

A harness assembles its whole context (persona, skills, agents, tools) into the first request to its model. An
endpoint that records that request and answers a 400 shows exactly what the harness loaded, with the real binary,
at zero tokens; a 400 is final for every client, so nothing retries with backoff. It speaks just enough HTTP/1.1:
a request line, headers, a `Content-Length` body (or a chunked one), one response, the connection closed.

`answer` turns the refusal into a turn: on an Anthropic (`/messages`) or OpenAI (`/chat/completions`) route it
calls the named tool once, the first time a request offers it, then answers a text that ends the turn — streamed
when the request streams. The loop completes, so the hooks of a turn fire. Any other route is still refused."""

from collections.abc import Mapping
from contextlib import asynccontextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Self

import anyio
import msgspec
from anyio.abc import ByteStream, SocketAttribute

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

##### DEFAULTS #####
HOST: str = "127.0.0.1"
### a 16 MB request at 64 KB a receive: the recursive read stays well under the interpreter's depth.
LIMIT: int = 16 * 1024 * 1024
REFUSAL: Final[bytes] = (
    b"HTTP/1.1 400 Bad Request\r\ncontent-type: application/json\r\ncontent-length: 70\r\nconnection: close\r\n\r\n"
    b'{"type":"error","error":{"type":"invalid_request_error","message":"x"}}'
)
TEXT: str = "ghost"
CALL: str = "call_ghost"


##### UTILITIES #####
def sse_capture(events: list[tuple[str, Any]]) -> bytes:
    """Server-sent events: `event:` lines when named, one `data:` line each."""
    return b"".join(
        (f"event: {name}\n".encode() if name else b"") + b"data: " + msgspec.json.encode(data) + b"\n\n"
        for name, data in events
    )


def anthropic_capture(model: str, call: Mapping[str, Any] | None, *, stream: bool) -> tuple[str, bytes]:
    """An Anthropic Messages answer: one `tool_use` block, or one text block; streamed as its event sequence."""
    block = (
        {"type": "tool_use", "id": CALL, "name": call["tool"], "input": dict(call.get("input") or {})}
        if call
        else {"type": "text", "text": TEXT}
    )
    stop = "tool_use" if call else "end_turn"
    message = {"id": "msg_ghost", "type": "message", "role": "assistant", "model": model, "stop_sequence": None}
    usage = {"input_tokens": 1, "output_tokens": 1}
    match stream:
        case False:
            return "application/json", msgspec.json.encode(
                message | {"content": [block], "stop_reason": stop, "usage": usage}
            )
        case _:
            delta = (
                {"type": "input_json_delta", "partial_json": msgspec.json.encode(block["input"]).decode()}
                if call
                else {"type": "text_delta", "text": TEXT}
            )
            opening = block | ({"input": {}} if call else {"text": ""})
            return "text/event-stream", sse_capture(
                [
                    (
                        "message_start",
                        {
                            "type": "message_start",
                            "message": message | {"content": [], "stop_reason": None, "usage": usage},
                        },
                    ),
                    ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": opening}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                    (
                        "message_delta",
                        {
                            "type": "message_delta",
                            "delta": {"stop_reason": stop, "stop_sequence": None},
                            "usage": usage,
                        },
                    ),
                    ("message_stop", {"type": "message_stop"}),
                ]
            )


def openai_capture(model: str, call: Mapping[str, Any] | None, *, stream: bool) -> tuple[str, bytes]:
    """An OpenAI Chat Completions answer: one tool call, or one text; streamed as chunks closed by `[DONE]`."""
    calls = (
        [
            {
                "index": 0,
                "id": CALL,
                "type": "function",
                "function": {
                    "name": call["tool"],
                    "arguments": msgspec.json.encode(dict(call.get("input") or {})).decode(),
                },
            }
        ]
        if call
        else []
    )
    said = {"role": "assistant"} | ({"tool_calls": calls} if call else {"content": TEXT})
    finish = "tool_calls" if call else "stop"
    head = {"id": "chatcmpl-ghost", "created": 0, "model": model}
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    match stream:
        case False:
            return "application/json", msgspec.json.encode(
                head
                | {
                    "object": "chat.completion",
                    "choices": [{"index": 0, "message": said, "finish_reason": finish}],
                    "usage": usage,
                }
            )
        case _:
            chunk = head | {"object": "chat.completion.chunk"}
            return "text/event-stream", sse_capture(
                [
                    ("", chunk | {"choices": [{"index": 0, "delta": said, "finish_reason": None}]}),
                    ("", chunk | {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}], "usage": usage}),
                ]
            ) + b"data: [DONE]\n\n"


def offered_capture(request: Mapping[str, Any]) -> frozenset[str]:
    """The tool names a request offers, in either protocol's shape."""
    return frozenset(
        tool.get("name") or (tool.get("function") or {}).get("name") or "" for tool in request.get("tools") or []
    )


##### TABLES #####
ROUTES: Final[Mapping[str, Callable[..., tuple[str, bytes]]]] = MappingProxyType(
    {
        "/messages": anthropic_capture,
        "/chat/completions": openai_capture,
    }
)


##### TYPES #####
class HttpCapture:
    """Satisfies CapturePort on a loopback port chosen by the kernel; `serve` opens it for the duration of a block."""

    __slots__ = ("_bodies", "_called", "_port", "_reply")

    def __init__(self) -> None:
        self._bodies: list[bytes] = []
        self._port = 0
        self._reply: Mapping[str, Any] | None = None
        self._called = False

    ##### PRIVATE METHODS #####

    @classmethod
    async def _serve_more(cls, stream: ByteStream, buffer: bytes, enough: Callable[[bytes], bool]) -> bytes:
        """`buffer` extended from the stream until `enough` holds, or the size limit is reached."""
        match enough(buffer) or len(buffer) >= LIMIT:
            case True:
                return buffer
            case _:
                return await cls._serve_more(stream, buffer + await stream.receive(), enough)

    @classmethod
    async def _serve_read(cls, stream: ByteStream) -> tuple[str, bytes]:
        """One request's path and body: headers to the blank line, then `Content-Length` bytes, or the chunks."""
        buffer = await cls._serve_more(stream, b"", lambda got: b"\r\n\r\n" in got)
        head, _, body = buffer.partition(b"\r\n\r\n")
        path = head.split(b"\r\n")[0].split(b" ")[1:2] or [b""]
        return path[0].decode(errors="replace").partition("?")[0], await cls._serve_body(stream, head, body)

    @classmethod
    async def _serve_body(cls, stream: ByteStream, head: bytes, body: bytes) -> bytes:
        headers = {
            name.strip().lower(): value.strip()
            for line in head.split(b"\r\n")[1:]
            for name, _, value in (line.partition(b":"),)
        }
        match (headers.get(b"content-length"), headers.get(b"transfer-encoding", b"").lower()):
            case (bytes() as length, _):
                full = await cls._serve_more(stream, body, lambda got: len(got) >= int(length))
                return full[: int(length)]
            case (None, b"chunked"):
                return cls._serve_unchunk(await cls._serve_more(stream, body, lambda got: got.endswith(b"0\r\n\r\n")))
            case _:
                return body

    @staticmethod
    def _serve_unchunk(raw: bytes) -> bytes:
        size, _, rest = raw.partition(b"\r\n")
        length = int(size, 16)
        return b"" if length == 0 else rest[:length] + HttpCapture._serve_unchunk(rest[length + 2 :])

    def _serve_answer(self, path: str, body: bytes) -> bytes:
        """The refusal, or — answering — the turn this route speaks: the reply's tool once, then text."""
        route = next((handler for suffix, handler in ROUTES.items() if path.endswith(suffix)), None)
        match (self._reply, route):
            case (Mapping() as reply, handler) if handler is not None:
                request = msgspec.json.decode(body or b"{}")
                tool = reply.get("tool")
                call = reply if tool and not self._called and tool in offered_capture(request) else None
                self._called = self._called or call is not None
                kind, payload = handler(str(request.get("model") or TEXT), call, stream=bool(request.get("stream")))
                return (
                    f"HTTP/1.1 200 OK\r\ncontent-type: {kind}\r\ncontent-length: {len(payload)}\r\n"
                    "connection: close\r\n\r\n"
                ).encode() + payload
            case _:
                return REFUSAL

    async def _serve_one(self, stream: ByteStream) -> None:
        async with stream:
            try:
                path, body = await self._serve_read(stream)
                self._bodies.append(body)
                await stream.send(self._serve_answer(path, body))
            except anyio.EndOfStream, anyio.BrokenResourceError, ValueError, msgspec.DecodeError:
                return

    ############################################################

    ##### PUBLIC #####

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self._port}"

    @property
    def port(self) -> int:
        return self._port

    def bodies(self) -> tuple[bytes, ...]:
        return tuple(self._bodies)

    def clear(self) -> None:
        self._bodies.clear()
        self._called = False

    def answer(self, reply: Mapping[str, Any] | None) -> None:
        """From now on, refuse (`None`) or answer: `{tool?, input?}` — the tool called once, then a closing text."""
        self._reply = reply
        self._called = False

    @asynccontextmanager
    async def serve(self) -> AsyncIterator[Self]:
        """Listening for the block, every connection answered in the background; closed whole on the way out."""
        listener = await anyio.create_tcp_listener(local_host=HOST, local_port=0)
        self._port = listener.extra(SocketAttribute.local_port)  # noqa: S610 — anyio typed attributes, not Django
        async with listener, anyio.create_task_group() as group:
            group.start_soon(listener.serve, self._serve_one)
            yield self
            group.cancel_scope.cancel()
