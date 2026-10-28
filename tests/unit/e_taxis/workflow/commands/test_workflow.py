"""tests/unit/e_taxis/workflow/commands/workflow: `taxis workflow run | list | check` through the real app.

Defect 5 of the legacy CLI: `workflow run` exited 0 when a step failed (only an `error` counted). Now any `fail` or
`error` exits 24 — after the full report is printed."""

from typing import TYPE_CHECKING

import msgspec
import pytest

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
    assert "1 of 5 workflow(s) do not read clean: broken" in err


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


def test_workflow_step_and_put_walk_a_run_a_harness_drives(
    taxis: Callable[..., tuple[int, str, str]], nous: Path, tmp_path: Path
) -> None:
    rundir, answer = tmp_path / "run", tmp_path / "answer.md"
    base = ("--workflow", "demo", "--rundir", str(rundir), "--nous", str(nous))
    answer.write_text("thought\n")
    said = [
        taxis("workflow", "step", "first", *base, "value=v", "apply=true"),
        taxis("workflow", "step", "first", *base),
        taxis("workflow", "step", "echo", *base),
        taxis("workflow", "put", "think", *base, "--file", str(answer)),
        taxis("workflow", "step", "last", *base),
    ]
    assert [(code, msgspec.json.decode(out.splitlines()[-1])["status"]) for code, out, _ in said] == [(0, "ok")] * 5
    assert (rundir / "value.txt").read_text() == "v"
    assert (rundir / "nodes" / "think" / "out.md").read_text() == "thought\n"


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ([("step", "echo")], (3, "skip", "upstream first never ran")),
        ([("step", "first"), ("drop", "value.txt"), ("step", "echo")], (24, "fail", "")),
        ([("put", "first")], (24, "error", "first is a command step")),
    ],
    ids=["never-ran", "command-fails", "put-on-a-command"],
)
def test_workflow_step_exits_by_status(
    taxis: Callable[..., tuple[int, str, str]],
    nous: Path,
    tmp_path: Path,
    steps: list[tuple[str, str]],
    expected: tuple[int, str, str],
) -> None:
    rundir, answer = tmp_path / "run", tmp_path / "answer.md"
    base = ("--workflow", "demo", "--rundir", str(rundir), "--nous", str(nous))
    answer.write_text("x")
    actions = {
        "step": lambda node: taxis("workflow", "step", node, *base, "value=v"),
        "put": lambda node: taxis("workflow", "put", node, *base, "--file", str(answer)),
        "drop": lambda name: ((rundir / name).unlink(), (0, "", ""))[1],
    }
    code, out, _ = [actions[kind](arg) for kind, arg in steps][-1]
    line = msgspec.json.decode(out.splitlines()[-1])
    assert (code, line["status"], expected[2] in line["reason"]) == (expected[0], expected[1], True)


def test_workflow_step_refuses_an_unknown_step(
    taxis: Callable[..., tuple[int, str, str]], nous: Path, tmp_path: Path
) -> None:
    code, _, err = taxis(
        "workflow", "step", "nope", "--workflow", "demo", "--rundir", str(tmp_path), "--nous", str(nous)
    )
    assert (code, "no step 'nope'" in err) == (23, True)
