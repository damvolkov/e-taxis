"""tests/unit/e_taxis/workflow/plane/tasks: a skill without a set idles, which `needs` reads as coverage."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.plane import Cadence, Target
from e_taxis.workflow.models.run import Status

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun


async def test_tasks_absent_set_idles(plane_run: PlaneRun, plane_nous: Path) -> None:
    (plane_nous / "core/tekton/evals/tasks/algo-py-core.md").unlink()
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (), Cadence.COMMIT)
    (run,) = [run for run in report.runs if run.node == "tasks"]
    assert (run.status, run.reason) == (Status.IDLE, "no task set")
    assert "no task set" in [need.detail for need in report.needs["algo-py-core"]]
