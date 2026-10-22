"""reload: the phantom raised again shows the absorbed core, the learner's regions, and none of what was dropped."""

from __future__ import annotations

from ops.models.trial import Judgement, Sight


async def test_reload_shows_every_rendered_entity(resight: tuple[Sight, str]) -> None:
    sight, _ = resight
    assert sight.ok, {item.entity: item.missing[:5] for item in sight.evidence if not item.ok}


async def test_reload_honours_every_mutation(outcomes: Judgement) -> None:
    wrong = [(o.mutation.kind, o.mutation.expect, o.core, o.harness) for o in outcomes.outcomes if not o.ok]
    assert not wrong, wrong
