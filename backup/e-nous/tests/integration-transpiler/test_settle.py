"""settle: after absorb, a second apply leaves core and harness with nothing to move."""

from __future__ import annotations

from ops.models.trial import Settle


async def test_settle_reapplies(settled: Settle) -> None:
    assert settled.apply.ok, settled.apply.stderr or settled.apply.stdout[-2000:]


async def test_settle_leaves_nothing_to_move(settled: Settle) -> None:
    assert settled.ok, f"moves {settled.moves} · {settled.plan.stdout[-2000:]}"
