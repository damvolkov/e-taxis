"""tests/unit/e_taxis/workflow/services/run: a workflow end to end — real bash steps, a fake agent, the run folder."""

from typing import TYPE_CHECKING, Any

import anyio
import msgspec
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.models.error import LockError, RunFailedError, WorkflowError
from e_taxis.workflow.models.run import RunManifest, Status

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.run import WorkflowRun


async def test_run_demo_end_to_end(workflow_run: WorkflowRun, nous: Path, agent) -> None:
    value = 'it\'s "$(touch pwned)"\nsecond line'
    report = await workflow_run.run(GitNous(nous, None), "demo", {"value": value})
    by = {run.node: run for run in report.runs}
    folder = nous / ".reports" / "workflows" / "demo" / report.manifest.run_id
    assert [run.node for run in report.runs] == ["first", "echo", "think", "last"]
    assert [by[n].status for n in ("first", "echo", "think", "last")] == [Status.OK, Status.OK, Status.OK, Status.IDLE]
    assert (folder / "value.txt").read_text() == value
    assert (folder / "nodes" / "echo" / "out.md").read_text() == value
    assert (folder / "nodes" / "first" / "out.md").read_text() == f"wrote {report.manifest.run_id}\n"
    assert not (nous / "pwned").exists()
    assert agent.calls[0]["readonly"]
    assert report.manifest.run_id.endswith("-workflow-demo-worktree")
    assert report.folder == str(folder)
    assert report.broken == ()
    assert "| last | idle | — |" in (folder / "report.md").read_text()
    assert msgspec.json.decode((folder / "run.json").read_bytes(), type=RunManifest).params == {
        "value": value,
        "apply": "false",
    }


async def test_run_pins_the_checkout_head(workflow_run: WorkflowRun, nous: Path) -> None:
    git = ("git", "-C", str(nous), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false")
    _ = [await anyio.run_process((*git, *args)) for args in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "n"))]
    report = await workflow_run.run(GitNous(nous, None), "demo", {"apply": "true"})
    assert len(report.manifest.base_sha) == 40
    assert report.manifest.run_id.endswith(report.manifest.base_sha[:7])
    assert report.runs[-1].status is Status.OK


async def test_run_failed_step_is_broken_and_still_reported(workflow_run: WorkflowRun, nous: Path, agent) -> None:
    agent.failing.add("builder")
    report = await workflow_run.run(GitNous(nous, None), "demo", {"apply": "true"})
    assert [(run.node, run.status) for run in report.broken] == [("think", Status.FAIL)]
    assert report.runs[-1].status is Status.SKIP
    assert "**fail 1 · ok 2 · skip 1 · 0 tokens**" in report.markdown


async def test_run_loop_closes_and_idles_the_rest(workflow_run: WorkflowRun, nous: Path) -> None:
    report = await workflow_run.run(GitNous(nous, None), "looped", {})
    by = {run.node: run for run in report.runs}
    assert (by["check_1"].reason, by["check_2"].reason) == ("loop open", "loop closed")
    assert (by["work_3"].status, by["after_3"].status) == (Status.IDLE, Status.IDLE)
    assert by["report"].status is Status.OK
    assert (
        nous / ".reports" / "workflows" / "looped" / report.manifest.run_id / "passes.txt"
    ).read_text() == "pass 1\npass 2\n"


async def test_run_refuses_an_undeclared_parameter_before_anything(workflow_run: WorkflowRun, nous: Path) -> None:
    with pytest.raises(WorkflowError, match="undeclared parameter"):
        await workflow_run.run(GitNous(nous, None), "demo", {"ghost": "1"})
    assert not (nous / ".reports").exists()


async def test_run_held_checkout_fails_after_the_wait(
    workflow_run: WorkflowRun, nous: Path, held: Callable[[Path], Any]
) -> None:
    async with held(workflow_run.reports(nous) / ".lock"):
        with pytest.raises(LockError):
            await workflow_run.run(GitNous(nous, None), "demo", {})


async def test_run_launch_rebuilds_the_report_from_what_the_harness_walked(
    workflow_run: WorkflowRun, nous: Path, tmp_path: Path, walking
) -> None:
    report = await workflow_run.launch(GitNous(nous, None), "demo", {"value": "v"}, walking, cwd=tmp_path)
    folder = tmp_path / ".reports" / "workflows" / "demo"
    assert [(run.node, run.status) for run in report.runs] == [
        ("first", Status.OK),
        ("echo", Status.OK),
        ("think", Status.OK),
        ("last", Status.IDLE),
    ]
    assert walking.seen[0][2] == ("builder",)
    assert (await anyio.Path(report.folder, "report.md").read_text()).endswith("## The harness said\n\nwalked\n")
    assert report.folder.startswith(str(folder))


async def test_run_launch_fails_without_the_declared_output(
    workflow_run: WorkflowRun, nous: Path, tmp_path: Path, standing
) -> None:
    with pytest.raises(RunFailedError, match="without the declared output"):
        await workflow_run.launch(GitNous(nous, None), "demo", {}, standing, cwd=tmp_path)


async def test_run_project_empty_is_the_git_root(workflow_run: WorkflowRun, nous: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "deep").mkdir(parents=True)
    await anyio.run_process(["git", "init", "-q", str(repo)])
    report = await workflow_run.run(GitNous(nous, None), "rooted", {}, cwd=repo / "deep")
    folder = nous / ".reports" / "workflows" / "rooted" / report.manifest.run_id
    assert (folder / "project.txt").read_text() == str(repo)


async def test_run_project_outside_git_is_refused(workflow_run: WorkflowRun, nous: Path, tmp_path: Path) -> None:
    with pytest.raises(WorkflowError, match="is in no git project"):
        await workflow_run.run(GitNous(nous, None), "rooted", {}, cwd=tmp_path)
