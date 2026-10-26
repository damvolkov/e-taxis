"""memory: the phantom's memory pipeline over the applied tree — a note stored, embedded, sealed into a tree."""

from __future__ import annotations

import pytest

from ops.models.trial import Memory


async def test_memory_stores_embeds_and_seals(remembered: Memory | None) -> None:
    if remembered is None:
        pytest.skip("the recipe declares no memory")
    assert remembered.ok, remembered
