"""tests/unit/e_taxis/workflow/adapters/runner: one Messages request — the tier's model, the context as `system`, the
key as a header — and only `text` blocks as the answer; anything but a message is a ProviderError."""

import pytest

from e_taxis.workflow.adapters.runner import AnthropicRunner
from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.error import ProviderError
from e_taxis.workflow.models.run import Reply

MESSAGE = (
    b'{"content": [{"type": "thinking", "thinking": "hm"}, {"type": "text", "text": "use "},'
    b' {"type": "text", "text": "bisect"}], "usage": {"input_tokens": 11, "output_tokens": 4}}'
)


async def test_runner_complete_reads_the_text_blocks(messages, endpoint: Endpoint) -> None:
    messages.answer = MESSAGE
    runner = AnthropicRunner(tokens=64, limit=5.0)
    reply = await runner.complete(endpoint, "search", system="the skill")
    ((path, headers, body),) = messages.seen
    assert reply == Reply(text="use bisect", tokens=15)
    assert (path, headers["x-api-key"], headers["anthropic-version"]) == ("/v1/messages", "sk-k", "2023-06-01")
    assert body == {
        "model": "qwen",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "search"}],
        "system": "the skill",
    }


async def test_runner_complete_without_system_sends_none(messages, endpoint: Endpoint) -> None:
    messages.answer = MESSAGE
    await AnthropicRunner(tokens=64, limit=5.0).complete(endpoint, "search")
    assert "system" not in messages.seen[0][2]


async def test_runner_complete_refuses_an_error_body(messages, endpoint: Endpoint) -> None:
    messages.answer = b'{"type": "error", "error": {"message": "overloaded"}}'
    with pytest.raises(ProviderError, match="overloaded"):
        await AnthropicRunner(tokens=64, limit=5.0).complete(endpoint, "search")


async def test_runner_complete_names_an_unreachable_endpoint() -> None:
    dead = Endpoint(base_url="http://127.0.0.1:9/v1", key="k", model="m")
    with pytest.raises(ProviderError, match=r"127\.0\.0\.1:9/v1/messages"):
        await AnthropicRunner(tokens=64, limit=5.0).complete(dead, "search")
