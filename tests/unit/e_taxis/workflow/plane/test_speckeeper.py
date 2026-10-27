"""tests/unit/e_taxis/workflow/plane/speckeeper: the spec maintainer, briefed with the signals the evaluation recorded
(never fetched again), edits the sandbox; git measures what it touched; a write into the real checkout refuses it."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.metrics import GradeMetrics, ProposalMetrics
from e_taxis.workflow.models.plane import Cadence, Target
from e_taxis.workflow.models.run import Status

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

SPEC = "specs/tekton/claudecode.yaml"


async def test_speckeeper_acts_on_the_recorded_signals(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    evaluation = await plane_run.evaluate(plane_nous, Target.SPEC, ("claudecode",), Cadence.COMMIT)
    agent.effect = lambda tree: (tree / SPEC).write_text((tree / SPEC).read_text() + "\n# collated\n")
    report = await plane_run.enhance(plane_nous, Target.SPEC, (), Cadence.COMMIT, source=evaluation.manifest.run_id)
    (keeper,) = [run for run in report.runs if run.node == "speckeeper"]
    assert keeper.status is Status.OK
    assert isinstance(keeper.metrics, ProposalMetrics)
    assert keeper.metrics.files == (SPEC,)
    assert '"upstream"' in agent.calls[0]["prompt"]
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert isinstance(grade.metrics, GradeMetrics)
    assert grade.metrics.grade == "deepening"


async def test_speckeeper_status_move_weighs_surface(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    agent.effect = lambda tree: (tree / SPEC).write_text((tree / SPEC).read_text() + "\nstatus: ready\n")
    report = await plane_run.enhance(plane_nous, Target.SPEC, ("claudecode",), Cadence.COMMIT, directive="promote it")
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert isinstance(grade.metrics, GradeMetrics)
    assert (grade.metrics.grade, grade.metrics.bump) == ("surface", "minor")
    assert "Directive from the maintainer" in agent.calls[0]["prompt"]


async def test_speckeeper_writing_the_checkout_is_refused(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    agent.effect = lambda tree: (plane_nous / "LEAK.md").write_text("x\n")
    report = await plane_run.enhance(plane_nous, Target.SPEC, ("claudecode",), Cadence.COMMIT, directive="go")
    (keeper,) = [run for run in report.runs if run.node == "speckeeper"]
    assert (keeper.status, keeper.reason) == (Status.FAIL, "wrote into the real checkout: LEAK.md")


async def test_speckeeper_without_signal_or_directive_idles(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    report = await plane_run.enhance(plane_nous, Target.SPEC, ("claudecode",), Cadence.COMMIT, manual=True)
    (keeper,) = [run for run in report.runs if run.node == "speckeeper"]
    assert (keeper.status, keeper.reason) == (Status.IDLE, "no drift signal and no directive")
    assert agent.calls == []
