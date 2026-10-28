"""tests/unit/e_taxis/workflow/commands/workflow: `taxis workflow run | list | check` through the real app.

Defect 5 of the legacy CLI: `workflow run` exited 0 when a step failed (only an `error` counted). Now any `fail` or
`error` exits 24 — after the full report is printed."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_workflow_list_shows_every_workflow(taxis: Callable[..., tuple[int, str, str]], nous: Path) -> None:
    code, out, _ = taxis("workflow", "list", "--nous", str(nous))
    assert code == 0
    assert "demo — Every kind of step" in out
    assert "  params value · apply" in out
    assert "broken — ✗ broken: a: unknown agent nobody" in out


def test_workflow_check_names_what_does_not_read(taxis: Callable[..., tuple[int, str, str]], nous: Path) -> None:
    code, out, err = taxis("workflow", "check", "--nous", str(nous))
    assert code == 23
    assert "unknown agent nobody" in out
    assert "1 of 4 workflow(s) do not read clean: broken" in err


def test_workflow_check_clean_ones_exit_zero(taxis: Callable[..., tuple[int, str, str]], nous: Path) -> None:
    code, out, _ = taxis("workflow", "check", "demo", "looped", "--nous", str(nous))
    assert code == 0
    assert out.strip() == "workflows: 2 read clean"


def test_workflow_run_prints_the_report_and_exits_zero(
    taxis: Callable[..., tuple[int, str, str]], nous: Path, fake_agent_deps
) -> None:
    code, out, err = taxis("workflow", "run", "demo", "--nous", str(nous), "value=x y", "apply=true")
    assert code == 0
    assert "| last | ok | bash |" in out
    assert "/report.md" in out
    assert "  first" in err


def test_workflow_run_failed_step_exits_non_zero_after_the_report(
    taxis: Callable[..., tuple[int, str, str]], nous: Path, fake_agent_deps
) -> None:
    fake_agent_deps.failing.add("builder")
    code, out, err = taxis("workflow", "run", "demo", "--nous", str(nous), "value=x")
    assert code == 24
    assert "| think | fail | opencode |" in out
    assert "1 step(s) failed: think (fail)" in err


def test_workflow_run_refuses_a_bare_token(taxis: Callable[..., tuple[int, str, str]], nous: Path) -> None:
    code, _, err = taxis("workflow", "run", "demo", "--nous", str(nous), "value")
    assert code == 23
    assert "parameters are name=value: value" in err
