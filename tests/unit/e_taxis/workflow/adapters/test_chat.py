"""tests/unit/e_taxis/workflow/adapters/chat: one structured completion — the schema strict, temperature 0, the key as a
bearer — and only a JSON object as the answer; anything else is a ProviderError."""

import msgspec
import pytest

from e_taxis.workflow.adapters.chat import WreqChat
from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.error import ProviderError

SCHEMA = {"type": "object", "properties": {"tech": {"type": "string"}}}


def completion(content: str) -> bytes:
    return msgspec.json.encode({"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 9}})


async def test_chat_structured_reads_the_object(messages, endpoint: Endpoint) -> None:
    messages.answer = completion('{"tech": "rtk"}')
    said = await WreqChat(5.0).structured(endpoint, "sys", "query", SCHEMA)
    ((path, headers, body),) = messages.seen
    assert said == ({"tech": "rtk"}, 9)
    assert (path, {k.lower(): v for k, v in headers.items()}["authorization"]) == (
        "/v1/chat/completions",
        "Bearer sk-k",
    )
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"] == {"name": "kwargs", "strict": True, "schema": SCHEMA}
    assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "query"}]


@pytest.mark.parametrize(
    ("answer", "problem"),
    [(completion('["rtk"]'), "not an object"), (b"<html>", "no structured answer"), (completion(""), "no structured")],
    ids=["array", "html", "empty"],
)
async def test_chat_structured_refuses(messages, endpoint: Endpoint, answer: bytes, problem: str) -> None:
    messages.answer = answer
    with pytest.raises(ProviderError, match=problem):
        await WreqChat(5.0).structured(endpoint, "sys", "query", SCHEMA)


async def test_chat_structured_names_a_dead_endpoint() -> None:
    dead = Endpoint(base_url="http://127.0.0.1:9/v1", key="k", model="m")
    with pytest.raises(ProviderError, match=r"127\.0\.0\.1:9"):
        await WreqChat(2.0).structured(dead, "sys", "query", SCHEMA)
