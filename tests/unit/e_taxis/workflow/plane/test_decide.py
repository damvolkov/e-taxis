"""tests/unit/e_taxis/workflow/plane/decide: the heaviest finding wins — a gate never run holds, a target without a
ceiling proposes, a missing grade or intake reads as nothing measured; a green effect or routing gate is read, not
counted."""

from typing import TYPE_CHECKING, Any

import pytest
from msgspec.structs import replace

from e_taxis.workflow.models.metrics import (
    ActivationMetrics,
    CandidateMetrics,
    DecisionMetrics,
    EffectMetrics,
    GradeMetrics,
    Interval,
    Score,
)
from e_taxis.workflow.models.plane import NodeCard, NodeSpec, Role, Target
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.plane.decide import PlaneDecide

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

CARD = NodeCard(role=Role.DECIDE, summary="d")
DECIDE = NodeSpec(id="decide", use="decide", card=CARD, params={"gates": "law,probe"})
CHANGED = Outcome(status=Status.OK, metrics=CandidateMetrics(out="/c", changed=("a",), fixpoint=True))
MEASURED = NodeSpec(id="decide", use="decide", card=CARD, params={"gates": "effect,activation_candidate"})
ROUTING = ActivationMetrics(
    tree="base",
    mode="activation",
    backend="b",
    passed=9,
    total=10,
    rate=90.0,
    interval=Interval(70.0, 97.0),
    recall=(5, 5),
    precision=(4, 5),
    unmeasured=0,
)
ROUTED = Outcome(status=Status.OK, metrics=ROUTING)


async def test_decide_a_gate_never_run_holds(
    plane_state: Callable[..., Any], plane_record: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(DECIDE)
    await plane_record(state, "candidate", "s1", CHANGED)
    await plane_record(state, "law", "s1", Outcome(status=Status.OK))
    outcome = await PlaneDecide({"skill": "guidance"}).run(plane_context(state, "decide"))
    assert outcome.metrics == DecisionMetrics(
        decision="hold", reasons=("law green", "probe: never ran"), grade="", bump=""
    )


async def test_decide_target_without_ceiling_proposes(
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
) -> None:
    state = await plane_state(DECIDE, target=Target.TOOL, nous=str(plane_nous))
    await plane_record(state, "candidate", "s1", CHANGED)
    await plane_record(state, "law", "s1", Outcome(status=Status.OK))
    await plane_record(state, "probe", "s1", Outcome(status=Status.OK))
    grade = GradeMetrics(changes=(), grade="cosmetic", bump="patch")
    await plane_record(state, "grade", "s1", Outcome(status=Status.OK, metrics=grade))
    outcome = await PlaneDecide({"skill": "guidance"}).run(plane_context(state, "decide"))
    assert isinstance(outcome.metrics, DecisionMetrics)
    assert (outcome.metrics.decision, outcome.metrics.bump) == ("propose", "patch")
    assert outcome.metrics.reasons[-1] == "grade cosmetic above ceiling none"


EFFECT = EffectMetrics(
    split="test",
    tasks=6,
    seeds=3,
    base=Score(0.5, 0.5),
    candidate=Score(0.6, 0.6),
    delta=Score(0.1, 0.1),
    hard=Interval(-0.1, 0.1),
    soft=Interval(-0.1, 0.2),
)


@pytest.mark.parametrize(
    ("effect", "decision", "reason"),
    [
        (replace(EFFECT, tasks=2), "propose", "underpowered"),
        (replace(EFFECT, soft=Interval(-0.4, -0.1)), "reject", "worse"),
        (replace(EFFECT, soft=Interval(0.05, 0.2)), "propose", "better"),
        (EFFECT, "propose", "inconclusive"),
    ],
    ids=["underpowered", "worse", "better", "inconclusive"],
)
async def test_decide_reads_the_effect(
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
    effect: EffectMetrics,
    decision: str,
    reason: str,
) -> None:
    state = await plane_state(MEASURED)
    await plane_record(state, "candidate", "s1", CHANGED)
    await plane_record(state, "effect", "s1", Outcome(status=Status.OK, metrics=effect))
    await plane_record(state, "activation_candidate", "s1", ROUTED)
    outcome = await PlaneDecide({}).run(plane_context(state, "decide"))
    assert isinstance(outcome.metrics, DecisionMetrics)
    ### no ceiling for a skill here: even a better effect stops at propose, the reading still says why.
    assert outcome.metrics.decision == decision
    assert any(line.startswith(reason) for line in outcome.metrics.reasons)


@pytest.mark.parametrize(("base", "decision"), [(Interval(98.0, 100.0), "reject"), (Interval(60.0, 99.0), "propose")])
async def test_decide_reads_routing_against_the_base(
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
    base: Interval,
    decision: str,
) -> None:
    state = await plane_state(MEASURED)
    await plane_record(state, "candidate", "s1", CHANGED)
    await plane_record(
        state, "effect", "s1", Outcome(status=Status.OK, metrics=replace(EFFECT, soft=Interval(0.1, 0.2)))
    )
    await plane_record(state, "activation_candidate", "s1", ROUTED)
    reference = replace(ROUTING, interval=base)
    await plane_record(state, "activation_base", "s1", Outcome(status=Status.OK, metrics=reference))
    outcome = await PlaneDecide({}).run(plane_context(state, "decide"))
    assert isinstance(outcome.metrics, DecisionMetrics)
    assert outcome.metrics.decision == decision
