"""tests/unit/e_taxis/workflow/commands/eval: `taxis eval run | graph | needs` through the real app, on the mini
checkout; the scanner, the agent and the trial are the test plane's fakes."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

type Taxis = Callable[..., tuple[int, str, str]]


def test_eval_run_prints_needs_and_report(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    code, out, err = taxis("eval", "run", "skill", "algo-py-core", "--nous", str(plane_nous), "--cadence", "commit")
    assert code == 0
    assert "algo-py-core            2 needs  coverage" in out
    assert "/report.md" in out
    assert "security" in err


def test_eval_run_exits_24_when_a_node_broke(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    (plane_nous / "core/tekton/skills/algo-py-core/skill.yaml").write_text("name: algo-py-core\nbogus: 1\n")
    code, _, err = taxis("eval", "run", "skill", "--nous", str(plane_nous), "--cadence", "commit")
    assert code == 24
    assert "render/·" in err


def test_eval_graph_prints_one_target(taxis: Taxis, plane_deps: PlaneRun) -> None:
    code, out, _ = taxis("eval", "graph", "spec")
    assert code == 0
    assert out.startswith("## evaluator/spec")
    assert "signals" in out


def test_eval_needs_exit_one_while_open(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    taxis("eval", "run", "agent", "--nous", str(plane_nous), "--cadence", "commit")
    code, out, err = taxis("eval", "needs", "agent", "--nous", str(plane_nous), "--owner", "agent")
    assert code == 1
    assert out.startswith("builder                 law")
    assert "open need(s)" in err


def test_eval_needs_none_for_an_owner(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    taxis("eval", "run", "agent", "--nous", str(plane_nous), "--cadence", "commit")
    code, out, _ = taxis("eval", "needs", "agent", "--nous", str(plane_nous), "--owner", "human")
    assert code == 0
    assert out.strip() == "no open human needs"


def test_eval_needs_without_a_run_exits_27(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    code, _, err = taxis("eval", "needs", "skill", "--nous", str(plane_nous))
    assert code == 27
    assert "no evaluator skill run 'latest'" in err


def test_eval_run_only_refuses_a_gate(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    code, _, err = taxis("eval", "run", "skill", "algo-py-core", "--nous", str(plane_nous), "--only", "law")
    assert code != 0
    assert "--only names no measure of skill: law" in err
