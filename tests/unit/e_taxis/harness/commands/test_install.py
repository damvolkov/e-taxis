"""tests/unit/e_taxis/commands/install: `install`, `apply` and `uninstall` as a user sees them — dry by default, written with
--yes into the temp HOME, journaled so `history undo` takes the run back."""

import json
from typing import TYPE_CHECKING

import msgspec
import pytest

if TYPE_CHECKING:
    from pathlib import Path

APPLY = ("apply", "--target", "claudecode", "--profile", "house")
ONLY = ("--only", "tool,env,guide")
OPEN = ("--accept-licence", "gated", "--confirm", "gated")


@pytest.mark.parametrize("extra", [(), ("--yes", "--dry-run")], ids=["default", "dry-run-wins"])
def test_install_apply_without_yes_prints_the_plan_and_writes_nothing(
    taxis, on_world, runner, claude_dir: Path, extra: tuple[str, ...]
) -> None:
    code, out, _ = taxis(*APPLY, *extra)
    assert code == 0
    assert all(word in out for word in ("tool", "install", "svc", "deferred", "gated", "blocked", "--yes"))
    assert (runner.calls, claude_dir.exists()) == ([], False)


def test_install_apply_dry_run_json_is_the_plan(taxis, on_world) -> None:
    code, out, _ = taxis(*APPLY, *ONLY, "--json")
    assert code == 0
    assert [step["id"] for step in msgspec.json.decode(out)["steps"]] == ["tool", "env", "guide"]


def test_install_apply_then_history_undo_puts_the_home_back(taxis, on_world, runner, claude_dir: Path) -> None:
    code, out, _ = taxis(*APPLY, *ONLY, "--yes")
    assert code == 0
    assert all(word in out for word in ("applied", "pass"))
    assert json.loads((claude_dir / "settings.json").read_text()) == {"env": {"TOOL_ON": "1"}}
    assert "e-taxis:guide" in (claude_dir / "CLAUDE.md").read_text()
    assert "apply" in taxis("history", "list")[1]
    code, out, _ = taxis("history", "undo")
    assert (code, "3 change(s) reverted" in out) == (0, True)
    assert list(claude_dir.iterdir()) == []
    assert runner.calls == [("uv", "tool", "install", "tool==1.0"), ("uv", "tool", "uninstall", "tool")]


def test_install_apply_json_report(taxis, on_world) -> None:
    code, out, _ = taxis(*APPLY, *ONLY, "--yes", "--json")
    report = msgspec.json.decode(out)
    assert (code, [step["status"] for step in report["steps"]]) == (0, ["applied"] * 3)


def test_install_apply_refuses_a_closed_gate(taxis, on_world, claude_dir: Path) -> None:
    code, _, err = taxis(*APPLY, "--yes")
    assert code == 10
    assert "gated needs --accept-licence gated" in err
    assert not claude_dir.exists()


def test_install_apply_opens_the_gate_with_flags_and_secrets(
    taxis, on_world, runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATED_TOKEN", "set")
    code, out, _ = taxis(*APPLY, *OPEN, "--yes")
    assert code == 0
    assert any(call[:3] == ("claude", "mcp", "add-json") for call in runner.calls)
    assert "deferred" in out


def test_install_apply_failure_exits_and_still_files_what_it_wrote(
    taxis, on_world, runner, claude_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATED_TOKEN", "set")
    runner.failing.add(("claude",))
    code, out, err = taxis(*APPLY, *OPEN, "--yes")
    assert code == 10
    assert ("failed" in out, "gated" in err) == (True, True)
    assert taxis("history", "undo")[0] == 0
    assert list(claude_dir.iterdir()) == []


def test_install_apply_failed_verify_exits(taxis, on_world) -> None:
    code, _, err = taxis("apply", "--target", "claudecode", "--profile", "flaky", "--yes")
    assert (code, "flaky" in err) == (10, True)


def test_install_uninstall_without_yes_plans(taxis, on_world, home: Path) -> None:
    (home / ".tool").touch()
    code, out, _ = taxis("uninstall", "tool", "--target", "claudecode")
    assert (code, "planned" in out, "--yes" in out) == (0, True, True)


def test_install_uninstall_then_history_undo(taxis, on_world, claude_dir: Path) -> None:
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# Me\n\n<!-- e-taxis:guide -->\nUse the tool.\n<!-- /e-taxis:guide -->\n")
    code, out, _ = taxis("uninstall", "guide", "--target", "claudecode", "--yes")
    assert (code, "removed" in out, (claude_dir / "CLAUDE.md").read_text()) == (0, True, "# Me\n")
    assert taxis("history", "undo")[0] == 0
    assert "e-taxis:guide" in (claude_dir / "CLAUDE.md").read_text()


@pytest.mark.parametrize(
    ("part", "message"), [("nope", "no entry nope serves claudecode"), ("here", "here")], ids=["unknown", "failed"]
)
def test_install_uninstall_failure_exits(taxis, on_world, part: str, message: str) -> None:
    code, _, err = taxis("uninstall", part, "--target", "claudecode", "--cascade", "--yes")
    assert (code, message in err) == (11, True)


def test_install_without_yes_prints_both_plans(taxis, on_world, brain_root: Path, home: Path) -> None:
    code, out, _ = taxis(
        "install", "--target", "claudecode", "--nous", str(brain_root), "--worktree", "--profile", "house"
    )
    assert code == 0
    assert all(word in out for word in ("CLAUDE.md", "missing", "tool", "gated"))
    assert not (home / ".claude").exists()


def test_install_json_prints_each_half(taxis, on_world, brain_root: Path) -> None:
    install = ("install", "--target", "claudecode", "--nous", str(brain_root), "--worktree", "--profile", "house")
    code, out, _ = taxis(*install, "--json")
    brain, world = (msgspec.json.decode(line) for line in out.splitlines())
    assert (code, "findings" in brain, "steps" in world) == (0, True, True)


def test_install_lands_brain_then_systems_in_one_undoable_run(
    taxis, on_world, brain_root: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATED_TOKEN", "set")
    install = ("install", "--target", "claudecode", "--nous", str(brain_root), "--worktree", "--profile", "house")
    code, out, _ = taxis(*install, *OPEN, "--yes")
    assert (code, "applied" in out) == (0, True)
    assert (home / ".claude/CLAUDE.md").is_file()
    assert [entry.split()[2] for entry in taxis("history", "list")[1].splitlines()[1:]] == ["install"]
    assert taxis("history", "undo")[0] == 0
    assert not (home / ".claude/CLAUDE.md").exists()


def test_install_systems_failure_still_undoes_the_brain(taxis, on_world, brain_root: Path, home: Path) -> None:
    install = ("install", "--target", "claudecode", "--nous", str(brain_root), "--worktree", "--profile", "flaky")
    code, _, err = taxis(*install, "--yes")
    assert (code, "flaky" in err) == (10, True)
    assert (home / ".claude/CLAUDE.md").is_file()
    assert taxis("history", "undo")[0] == 0
    assert not (home / ".claude/CLAUDE.md").exists()


def test_install_target_without_spec_skips_the_brain(taxis, on_world, brain_root: Path) -> None:
    code, out, _ = taxis("install", "--target", "system", "--nous", str(brain_root), "--worktree", "--profile", "house")
    assert (code, "no spec projects system" in out) == (0, True)
