"""absorb: what the harness wrote returns to core/ — only what it must, and nothing else."""

from __future__ import annotations

from ops.models.trial import Expect, Judgement, Run


async def test_absorb_runs(absorbed: Run) -> None:
    assert absorbed.ok, absorbed.stderr or absorbed.stdout[-2000:]


async def test_absorb_writes_exactly_the_absorbable(outcomes: Judgement) -> None:
    wrong = [
        (o.mutation.kind, o.mutation.slot)
        for o in outcomes.outcomes
        if o.core != (o.mutation.expect is Expect.ABSORBED)
    ]
    assert not wrong, wrong
