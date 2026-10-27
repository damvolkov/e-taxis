"""tests/unit/e_taxis/workflow/plane/needs: ledger rows read as typed needs — drift but not context, a break without
a reading, and nothing from a row that carries no reason to act."""

from typing import TYPE_CHECKING, Any

from e_taxis.workflow.models.metrics import Need, NeedsMetrics, SignalMetrics, SignalRow
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
