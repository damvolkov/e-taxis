"""adapters.capture: a fake model endpoint that keeps what a harness sent it — the eye of a phantom.

A harness assembles its whole context (persona, skills, agents, tools) into the first request to its model. An
endpoint that records that request and answers a 400 shows exactly what the harness loaded, with the real binary,
at zero tokens; a 400 is final for every client, so nothing retries with backoff. It speaks just enough HTTP/1.1:
a request line, headers, a `Content-Length` body (or a chunked one), one response, the connection closed."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final, Self

import anyio
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


##### TYPES #####
class HttpCapture:
    """Satisfies CapturePort on a loopback port chosen by the kernel; `serve` opens it for the duration of a block."""

    __slots__ = ("_bodies", "_port")

    def __init__(self) -> None:
        self._bodies: list[bytes] = []
        self._port = 0

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
    async def _serve_read(cls, stream: ByteStream) -> bytes:
        """One request's body: headers to the blank line, then `Content-Length` bytes, or the chunks to the last."""
        buffer = await cls._serve_more(stream, b"", lambda got: b"\r\n\r\n" in got)
        head, _, body = buffer.partition(b"\r\n\r\n")
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

    async def _serve_one(self, stream: ByteStream) -> None:
        async with stream:
            try:
                self._bodies.append(await self._serve_read(stream))
                await stream.send(REFUSAL)
            except anyio.EndOfStream, anyio.BrokenResourceError, ValueError:
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

    @asynccontextmanager
    async def serve(self) -> AsyncIterator[Self]:
        """Listening for the block, every connection answered in the background; closed whole on the way out."""
        listener = await anyio.create_tcp_listener(local_host=HOST, local_port=0)
        self._port = listener.extra(SocketAttribute.local_port)  # noqa: S610 — anyio typed attributes, not Django
        async with listener, anyio.create_task_group() as group:
            group.start_soon(listener.serve, self._serve_one)
            yield self
            group.cancel_scope.cancel()
