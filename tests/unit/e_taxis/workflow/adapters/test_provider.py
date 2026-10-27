"""tests/unit/e_taxis/workflow/adapters/provider: a tier → its provider's endpoint, the key read from the variable the
config names (never written in it); an unset variable or an undeclared tier is a ProviderError."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.adapters.provider import HouseProvider
from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.error import ProviderError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (
            "scout",
            Endpoint(
                base_url="https://maas/apps/anthropic/v1",
                key="sk-plan",
                model="qwen3.8-flash",
                openai_url="https://maas/compatible-mode/v1",
            ),
        ),
        ("local", Endpoint(base_url="http://localhost:45100/v1", key="local-dev", model="gemma4-26b-a4b")),
    ],
    ids=["secret", "literal"],
)
async def test_provider_endpoint(models: Path, tier: str, expected: Endpoint) -> None:
    assert await HouseProvider({"PLAN_KEY": "sk-plan"}).endpoint(models, tier) == expected


@pytest.mark.parametrize(
    ("environ", "tier", "why"),
    [({}, "scout", "PLAN_KEY is not set"), ({}, "planner", "resolves to no provider"), ({}, "ghost", "no provider")],
    ids=["unset-key", "unknown-tier", "unknown-alias"],
)
async def test_provider_endpoint_refuses(models: Path, environ: dict[str, str], tier: str, why: str) -> None:
    with pytest.raises(ProviderError, match=why):
        await HouseProvider(environ).endpoint(models, tier)
