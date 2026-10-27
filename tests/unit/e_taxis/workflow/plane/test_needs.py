"""tests/unit/e_taxis/workflow/plane/needs: ledger rows read as typed needs — drift but not context, a break without
a reading, nothing from a row that carries no reason to act; a routing case that did not hold, an effect the interval
cannot tell from zero and every task still failing under the skill."""

from typing import TYPE_CHECKING, Any

import msgspec

from e_taxis.workflow.models.metrics import (
    ActivationMetrics,
    EffectMetrics,
    Interval,
    Need,
    NeedsMetrics,
    Score,
    SignalMetrics,
    SignalRow,
)
from e_taxis.workflow.models.plane import NodeCard, NodeSpec, Role
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.plane.needs import PlaneNeeds

if TYPE_CHECKING:
    from collections.abc import Callable

NEEDS = NodeSpec(id="needs", use="needs", card=NodeCard(role=Role.DECIDE, summary="n"))


async def test_needs_reads_every_row(
    plane_state: Callable[..., Any], plane_record: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(NEEDS)
    signals = SignalMetrics(
        backend="b", signals=(SignalRow("upstream", "2.0", "moved"), SignalRow("core", "x", "context only"))
    )
    await plane_record(state, "signals", "s1", Outcome(status=Status.OK, metrics=signals))
    await plane_record(state, "render", "s1", Outcome(status=Status.ERROR, reason="boom"))
    await plane_record(state, "snapshot", "s1", Outcome(status=Status.OK))
    await plane_record(state, "law", "s2", Outcome(status=Status.ERROR, reason="other subject"))
    outcome = await PlaneNeeds().run(plane_context(state, "needs"))
    assert outcome.metrics == NeedsMetrics(
        needs=(Need("drift", "signals", "upstream/2.0: moved"), Need("broken", "render", "boom"))
    )


async def test_needs_reads_the_measures(
    plane_state: Callable[..., Any], plane_record: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(NEEDS)
    routed = ActivationMetrics(
        tree="base",
        mode="activation",
        backend="b",
        passed=1,
        total=2,
        rate=50.0,
        interval=Interval(10.0, 90.0),
        recall=(1, 1),
        precision=(0, 1),
        unmeasured=0,
        failures=("monta un makefile",),
    )
    effect = EffectMetrics(
        split="test",
        tasks=2,
        seeds=3,
        base=Score(0.5, 0.5),
        candidate=Score(0.5, 0.6),
        delta=Score(0.0, 0.1),
        hard=Interval(-0.2, 0.2),
        soft=Interval(-0.1, 0.3),
        per_task={"t2": (0.0, 1.0), "t1": (1.0, 0.5)},
        mode="value",
    )
    helps = msgspec.structs.replace(effect, soft=Interval(0.1, 0.3), per_task={})
    await plane_record(state, "activation", "s1", Outcome(status=Status.OK, metrics=routed))
    await plane_record(state, "effect", "s1", Outcome(status=Status.OK, metrics=effect))
    await plane_record(state, "effect", "s2", Outcome(status=Status.OK, metrics=helps))
    outcome = await PlaneNeeds().run(plane_context(state, "needs"))
    assert outcome.metrics == NeedsMetrics(
        needs=(
            Need("routing", "activation", "activation: monta un makefile"),
            Need("effect", "effect", "the skill does not measurably help: soft 0.50→0.60 [-0.100, +0.300]"),
            Need("effect", "effect", "task t1 fails under the skill (hard 0.50)"),
        )
    )
    assert (await PlaneNeeds().run(plane_context(state, "needs", subject="s2"))).metrics == NeedsMetrics(needs=())
