"""adapters.chat: one structured completion on an OpenAI-compatible endpoint — the house tier's, over wreq.

The answer is forced by the schema (`response_format: json_schema`, strict), so what comes back is an object to
validate, never prose to parse. The local vLLM serves the OpenAI API at its base URL; a hosted provider at its
OpenAI-compatible twin (`openai_url`). Temperature 0: the same request reads the same way. Anything but a JSON object
(a refusal, a transport failure, a malformed answer) is a ProviderError naming the endpoint."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import msgspec
import wreq

from e_taxis.workflow.adapters.runner import FAILURES
from e_taxis.workflow.models.error import ProviderError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.workflow.models.endpoint import Endpoint


##### TYPES #####
class ChatMessage(msgspec.Struct, frozen=True):
    content: str | None = None


class ChatChoice(msgspec.Struct, frozen=True):
    message: ChatMessage


class ChatUsage(msgspec.Struct, frozen=True):
    total_tokens: int = 0


class ChatCompletion(msgspec.Struct, frozen=True):
    """The slice of a chat completion the adapter reads."""

    choices: list[ChatChoice]
    usage: ChatUsage = ChatUsage()


class WreqChat:
    """Satisfies ChatPort; `limit` (seconds) bounds one request."""

    __slots__ = ("_limit",)

    def __init__(self, limit: float) -> None:
        self._limit = limit

    ##### PRIVATE METHODS #####

    async def _structured_post(self, url: str, body: Mapping[str, Any], key: str) -> bytes:
        client = wreq.Client(timeout=timedelta(seconds=self._limit))
        try:
            response = await client.post(url, json=dict(body), headers={"Authorization": f"Bearer {key}"})
            return await response.bytes()
        except FAILURES as exc:
            msg = f"{url}: {exc}"
            raise ProviderError(msg) from exc
        finally:
            client.close()

    ############################################################

    ##### PUBLIC #####

    async def structured(
        self, endpoint: Endpoint, system: str, user: str, schema: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        """The object the schema forces, and the tokens it cost."""
        url = f"{(endpoint.openai_url or endpoint.base_url).rstrip('/')}/chat/completions"
        body = {
            "model": endpoint.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "kwargs", "strict": True, "schema": schema},
            },
        }
        raw = await self._structured_post(url, body, endpoint.key)
        try:
            completion = msgspec.json.decode(raw, type=ChatCompletion)
            answer = msgspec.json.decode(completion.choices[0].message.content or "")
        except (msgspec.DecodeError, msgspec.ValidationError, IndexError) as odd:
            msg = f"{url}: no structured answer — {raw[:300]!r}"
            raise ProviderError(msg) from odd
        match answer:
            case dict():
                return answer, completion.usage.total_tokens
            case _:
                msg = f"{url}: the answer is not an object — {answer!r}"
                raise ProviderError(msg)
