"""adapters.downloader: one URL streamed to a file over wreq — redirects followed, bounded by a whole-request timeout.

The body goes to disk chunk by chunk, never whole in memory. wreq's errors share no base class, so the
ones a download can raise are named once here and all become a DownloadError."""

from datetime import timedelta
from typing import TYPE_CHECKING

import anyio
import wreq
from wreq import exceptions
from wreq.redirect import Policy

from e_taxis.models.error import DownloadError

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
REDIRECTS: int = 10
FAILURES: tuple[type[Exception], ...] = (
    exceptions.StatusError,
    exceptions.ConnectionError,
    exceptions.ConnectionResetError,
    exceptions.TimeoutError,
    exceptions.TlsError,
    exceptions.RequestError,
    exceptions.RedirectError,
    exceptions.BodyError,
    exceptions.DecodingError,
)


##### TYPES #####
class WreqDownloader:
    """Satisfies DownloaderPort; `timeout` (seconds) bounds the whole request, body included."""

    __slots__ = ("_timeout",)

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout

    async def fetch(self, url: str, dest: Path) -> None:
        client = wreq.Client(timeout=timedelta(seconds=self._timeout), redirect=Policy.limited(REDIRECTS))
        try:
            response = await client.get(url)
            response.raise_for_status()
            async with await anyio.open_file(dest, "wb") as out, response.stream() as chunks:
                ### the stream interleaves HTTP trailers (HeaderMap) with the body: only bytes are the file.
                body = (chunk async for chunk in chunks if isinstance(chunk, bytes))
                async for chunk in body:
                    await out.write(chunk)
        except FAILURES as exc:
            msg = f"{url}: {exc}"
            raise DownloadError(msg) from exc
        finally:
            client.close()
