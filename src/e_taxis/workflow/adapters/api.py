"""adapters.api: one GET against a public JSON API over wreq — never raising, so a dead source is a value, not a crash.

Every request names itself (`User-Agent`: crates.io refuses an anonymous one) and asks for JSON. A GitHub token,
when the settings hold one (`GH_TOKEN`), goes to api.github.com and nowhere else: unauthenticated, GitHub allows 60
requests an hour. wreq's errors share no base class, so the transport failures are named once (the downloader's
set) and every one becomes status 0 with its message."""

from datetime import timedelta
from typing import Final

import wreq
from wreq.redirect import Policy

from e_taxis.adapters.downloader import FAILURES, REDIRECTS
from e_taxis.workflow.models.assess import Fetched

##### DEFAULTS #####
AGENT: str = "e-taxis (radar-tech)"
GITHUB: str = "https://api.github.com/"
ACCEPT: Final[dict[str, str]] = {"User-Agent": AGENT, "Accept": "application/json"}


##### TYPES #####
class WreqApi:
    """Satisfies ApiPort; `timeout` (seconds) bounds each request, `token` authenticates GitHub only."""

    __slots__ = ("_timeout", "_token")

    def __init__(self, timeout: float, token: str = "") -> None:
        self._timeout = timeout
        self._token = token

    ##### PRIVATE METHODS #####

    def _get_headers(self, url: str) -> dict[str, str]:
        signed = bool(self._token) and url.startswith(GITHUB)
        return ACCEPT | ({"Authorization": f"Bearer {self._token}"} if signed else {})

    ############################################################

    ##### PUBLIC #####

    async def get(self, url: str) -> Fetched:
        client = wreq.Client(timeout=timedelta(seconds=self._timeout), redirect=Policy.limited(REDIRECTS))
        try:
            response = await client.get(url, headers=self._get_headers(url))
            body = await response.bytes()
        except FAILURES as exc:
            return Fetched(url=url, status=0, error=f"{type(exc).__name__}: {exc}")
        finally:
            client.close()
        link = response.headers.get("link") or b""
        return Fetched(url=url, status=response.status.as_int(), body=body, link=bytes(link).decode())
