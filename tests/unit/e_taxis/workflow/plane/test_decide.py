"""tests/unit/e_taxis/workflow/plane/decide: the heaviest finding wins — a gate never run holds, a target without a
ceiling proposes, a missing grade or intake reads as nothing measured."""

from typing import TYPE_CHECKING, Any

from e_taxis.workflow.models.metrics import CandidateMetrics, DecisionMetrics, GradeMetrics
from e_taxis.workflow.models.plane import NodeCard, NodeSpec, Role, Target
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.plane.decide import PlaneDecide

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

CARD = NodeCard(role=Role.DECIDE, summary="d")
DECIDE = NodeSpec(id="decide", use="decide", card=CARD, params={"gates": "law,probe"})
CHANGED = Outcome(status=Status.OK, metrics=CandidateMetrics(out="/c", changed=("a",), fixpoint=True))


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
