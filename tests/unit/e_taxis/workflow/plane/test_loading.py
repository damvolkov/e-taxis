"""tests/unit/e_taxis/workflow/plane/loading: the v2 trial's sights as a corpus reading — due nightly, red when an
entity the render declares never reached the fake model."""

from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.models.metrics import LoadingMetrics
from e_taxis.workflow.models.plane import Cadence, Target
from e_taxis.workflow.models.run import Status

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun


async def test_loading_reads_the_trial(plane_run: PlaneRun, plane_nous: Path, trial) -> None:
    report = await plane_run.evaluate(plane_nous, Target.CORPUS, (), Cadence.NIGHTLY)
    (loading,) = [run for run in report.runs if run.node == "loading"]
    assert (loading.status, loading.reason) == (Status.FAIL, "1 invisible, 1 probe(s) reached the model")
    assert loading.metrics == LoadingMetrics(backend="claudecode", declared=2, invisible=("skill:algo-py-core",))
    assert trial.backends == ["claudecode"]


async def test_loading_held_is_green(plane_run: PlaneRun, plane_nous: Path, trial) -> None:
    (sight,) = trial.report.sights
    trial.report = msgspec.structs.replace(trial.report, sights=(msgspec.structs.replace(sight, missing=()),))
    report = await plane_run.evaluate(plane_nous, Target.CORPUS, (), Cadence.WEEKLY)
    assert [(run.status, run.reason) for run in report.runs if run.node == "loading"] == [(Status.OK, "")]


async def test_loading_is_not_due_at_commit(plane_run: PlaneRun, plane_nous: Path, trial) -> None:
    report = await plane_run.evaluate(plane_nous, Target.CORPUS, (), Cadence.COMMIT)
    assert [run.status for run in report.runs if run.node == "loading"] == [Status.IDLE]
    assert trial.backends == []
