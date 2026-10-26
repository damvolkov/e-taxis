"""tests/unit/e_taxis/workflow/adapters/ledger: append-only JSONL — durable, indexed, replayed on open."""

from typing import TYPE_CHECKING, Any

from e_taxis.workflow.adapters.ledger import JsonlLedger
from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.metrics import LoopMetrics, LoopState
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Callable


async def test_ledger_replays_what_it_appended(state: Callable[..., Any], record: Callable[..., Any]) -> None:
    run = await state(StepSpec(id="a", run="x"))
    metrics = LoopMetrics(iteration=1, state=LoopState.OPEN, open=2, digest="d")
    await record(run, "a", Outcome(status=Status.FAIL, metrics=metrics))
    await record(run, "a", Outcome(status=Status.OK))
    replayed = await JsonlLedger.open(run.paths.ledger)
    assert [r.status for r in replayed.runs()] == [Status.FAIL, Status.OK]
    assert replayed.runs()[0].metrics == metrics
    assert getattr(replayed.latest("a"), "status", None) is Status.OK
    assert replayed.latest("ghost") is None
