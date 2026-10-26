"""load: a phantom of the real harness, raised over the applied tree, shows everything core rendered."""

from __future__ import annotations

from ops.models.trial import Sight


async def test_load_shows_every_rendered_entity(sight: Sight) -> None:
    missing = {
        item.entity: f"{item.seen}/{item.expected} · {item.missing[:5]}" for item in sight.evidence if not item.ok
    }
    assert sight.ok, missing


async def test_load_reaches_the_fake_llm_or_the_binary(sight: Sight) -> None:
    assert sight.runs and all(run.code is not None for run in sight.runs), [run.stderr[-500:] for run in sight.runs]
