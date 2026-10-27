"""adapters.runner: a bare completion on any Anthropic-Messages endpoint — the house provider's tier, over wreq.

No harness: no skills, no tools, no persona — the instrument the effect A/B needs, where the only context is the
one the node puts in `system`. Reasoning blocks are billed but never scored: only `text` blocks are the answer.
Anything but a message (a refusal, a transport failure) is a ProviderError naming the endpoint."""

from datetime import timedelta
from typing import TYPE_CHECKING

import msgspec
import wreq
from wreq import exceptions

from e_taxis.workflow.models.error import ProviderError
from e_taxis.workflow.models.run import Reply

if TYPE_CHECKING:
    from e_taxis.workflow.models.endpoint import Endpoint

##### DEFAULTS #####
VERSION: str = "2023-06-01"
TAIL: int = 300
FAILURES: tuple[type[Exception], ...] = (
    exceptions.ConnectionError,
    exceptions.ConnectionResetError,
    exceptions.TimeoutError,
    exceptions.TlsError,
    exceptions.RequestError,
    exceptions.BodyError,
)


##### TYPES #####
class MessageBlock(msgspec.Struct, frozen=True):
    type: str
    text: str = ""


class MessageUsage(msgspec.Struct, frozen=True):
    input_tokens: int = 0
    output_tokens: int = 0


class Message(msgspec.Struct, frozen=True):
    """The slice of a Messages response the runner reads."""

    content: list[MessageBlock]
    usage: MessageUsage = MessageUsage()


class AnthropicRunner:
    """Satisfies RunnerPort; `limit` (seconds) bounds one request, `tokens` the answer."""

    __slots__ = ("_limit", "_tokens")

    def __init__(self, *, tokens: int, limit: float) -> None:
        self._tokens = tokens
        self._limit = limit

    ##### PRIVATE METHODS #####

    async def _complete_post(self, url: str, body: dict[str, object], headers: dict[str, str]) -> bytes:
        client = wreq.Client(timeout=timedelta(seconds=self._limit))
        try:
            response = await client.post(url, json=body, headers=headers)
            return await response.bytes()
        except FAILURES as exc:
            msg = f"{url}: {exc}"
            raise ProviderError(msg) from exc
        finally:
            client.close()

    ############################################################

    ##### PUBLIC #####

    async def complete(self, endpoint: Endpoint, prompt: str, *, system: str = "") -> Reply:
        """One message; repeats are independent samples."""
        url = f"{endpoint.base_url.rstrip('/')}/messages"
        body = {
            "model": endpoint.model,
            "max_tokens": self._tokens,
            "messages": [{"role": "user", "content": prompt}],
            **({"system": system} if system else {}),
        }
        headers = {"x-api-key": endpoint.key, "anthropic-version": VERSION, "content-type": "application/json"}
        raw = await self._complete_post(url, body, headers)
        try:
            message = msgspec.json.decode(raw, type=Message)
        except msgspec.DecodeError as odd:
            msg = f"{url}: {raw[:TAIL]!r}"
            raise ProviderError(msg) from odd
        return Reply(
            text="".join(block.text for block in message.content if block.type == "text"),
            tokens=message.usage.input_tokens + message.usage.output_tokens,
        )
