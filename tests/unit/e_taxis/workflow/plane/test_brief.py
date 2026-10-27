"""tests/unit/e_taxis/workflow/plane/brief: no intake, no lesson."""

from typing import TYPE_CHECKING, Any

from e_taxis.workflow.models.metrics import ProposalMetrics
from e_taxis.workflow.models.plane import NodeCard, NodeSpec, Role
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.plane.brief import PlaneBrief

if TYPE_CHECKING:
    from collections.abc import Callable

BRIEF = NodeSpec(id="brief", use="brief", card=NodeCard(role=Role.PROPOSE, summary="b"))


async def test_brief_without_intake_is_idle(plane_state: Callable[..., Any], plane_context: Callable[..., Any]) -> None:
    outcome = await PlaneBrief().run(plane_context(await plane_state(BRIEF), "brief"))
    assert (outcome.status, outcome.metrics) == (Status.IDLE, ProposalMetrics(proposer="brief", files=(), lessons=()))
