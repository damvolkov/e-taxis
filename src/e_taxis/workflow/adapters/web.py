"""adapters.web: the open web over wreq, read as a browser reads it — a page's text, a multipart post.

LinkedIn and most publishers answer a script a login wall or a 999; wreq's browser emulation (TLS and HTTP/2
fingerprints, headers) is what makes a public page answer as it does in a browser. One client per call, closed
after it; a whole-request timeout bounds each. wreq's errors share no base class, so the ones a request can raise
are named once here and all become a SweepError."""

from datetime import timedelta
from typing import TYPE_CHECKING

import wreq
from wreq import Multipart, Part, exceptions
from wreq.emulation import Profile
from wreq.redirect import Policy

from e_taxis.workflow.models.error import SweepError

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
TIMEOUT: float = 30.0
REDIRECTS: int = 10
BROWSER: Profile = Profile.Chrome137
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
class WreqWeb:
    """Satisfies WebPort; `timeout` (seconds) bounds each whole request, body included."""

    __slots__ = ("_timeout",)

    def __init__(self, timeout: float = TIMEOUT) -> None:
        self._timeout = timeout

    ##### PRIVATE METHODS #####

    def _common_client(self) -> wreq.Client:
        return wreq.Client(
            timeout=timedelta(seconds=self._timeout), redirect=Policy.limited(REDIRECTS), emulation=BROWSER
        )

    ############################################################

    ##### PUBLIC #####

    async def get(self, url: str) -> str:
        client = self._common_client()
        try:
            response = await client.get(url)
            response.raise_for_status()
            return await response.text()
        except FAILURES as exc:
            msg = f"{url}: {exc}"
            raise SweepError(msg) from exc
        finally:
            client.close()

    async def post(self, url: str, *, fields: Mapping[str, str], files: Mapping[str, tuple[str, bytes]]) -> None:
        parts = (
            *(Part(name, value) for name, value in fields.items()),
            *(Part(name, body, filename=filename) for name, (filename, body) in files.items()),
        )
        client = self._common_client()
        try:
            response = await client.post(url, multipart=Multipart(*parts))
            response.raise_for_status()
        except FAILURES as exc:
            msg = f"{url}: {exc}"
            raise SweepError(msg) from exc
        finally:
            client.close()
