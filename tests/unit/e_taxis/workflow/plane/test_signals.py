"""tests/unit/e_taxis/workflow/plane/signals: a backend's drift is the v2 check's `signal` findings for it."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.metrics import SignalMetrics
from e_taxis.workflow.models.plane import Cadence, Target

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun


async def test_signals_become_drift_needs(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.evaluate(plane_nous, Target.SPEC, ("claudecode", "openhuman"), Cadence.COMMIT)
    rows = {run.subject: run.metrics for run in report.runs if run.node == "signals"}
    assert isinstance(rows["claudecode"], SignalMetrics)
    assert rows["claudecode"].signals[0].category == "upstream"
    assert [need.kind for need in report.needs["claudecode"]] == ["drift"]
    assert report.needs["openhuman"] == ()
