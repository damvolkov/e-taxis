"""tests/unit/e_taxis/commands/brain: `brain` and `install` as a user sees them — dry by default, written with --yes into
the temp Claude tree, and `history undo` puts the tree back byte for byte, directories included."""

import json
from typing import TYPE_CHECKING

import msgspec
import pytest

if TYPE_CHECKING:
    from pathlib import Path

LIVE = {
    "settings.json": '{"statusLine": {"type": "command"}}\n',
    "CLAUDE.md": "# Old\n\n## Local notes\n\nmine\n",
    "agents/scout.md": "edited by hand\n",
}
OPEN = ("--accept-licence", "gated", "--confirm", "gated")


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every path under root: a file's bytes, a directory as None."""
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in sorted(root.rglob("*"))}


@pytest.fixture
def live(claude_dir: Path) -> dict[str, bytes | None]:
    """A Claude tree already in use: a foreign settings key, a local section, a hand edit."""
    _ = [
        (claude_dir / path).parent.mkdir(parents=True, exist_ok=True) or (claude_dir / path).write_text(text)
        for path, text in LIVE.items()
    ]
    return _tree(claude_dir)


def _brain(core_repo: Path, *extra: str) -> tuple[str, ...]:
    return ("brain", "--target", "claudecode", "--nous", str(core_repo), *extra)


def test_brain_without_yes_prints_the_plan_and_writes_nothing(taxis, core_repo: Path, live, claude_dir: Path) -> None:
    code, out, _ = taxis(*_brain(core_repo))
    assert code == 0
    assert all(word in out for word in ("CLAUDE.md", "overwrite", "add", "mcp:local", "--yes"))
    assert _tree(claude_dir) == live


def test_brain_json_is_the_plan(taxis, core_repo: Path) -> None:
    code, out, _ = taxis(*_brain(core_repo, "--json"))
    plan = msgspec.json.decode(out)
    assert (code, plan["target"], len(plan["moves"])) == (0, "claudecode", 17)


def test_brain_yes_then_history_undo_puts_the_tree_back(taxis, core_repo: Path, live, runner, claude_dir: Path) -> None:
    code, out, _ = taxis(*_brain(core_repo, "--yes"))
    assert (code, "--yes" in out) == (0, False)
    settings = json.loads((claude_dir / "settings.json").read_text())
    assert (settings["statusLine"], settings["model"]) == ({"type": "command"}, "opus")
    assert (claude_dir / "CLAUDE.md").read_text().endswith("## Local notes\n\nmine")
    assert "brain" in taxis("history", "list")[1]
    assert taxis("history", "undo")[0] == 0
    ### the owned keys go back by value: settings.json is the same JSON, re-indented by the merge that wrote it.
    after = _tree(claude_dir)
    assert json.loads(after.pop("settings.json") or b"") == json.loads(live.pop("settings.json") or b"")
    assert after == live
    assert runner.calls[-1] == ("claude", "mcp", "remove", "local")


def test_brain_worktree_reads_uncommitted_and_a_faithful_tree_holds_the_core(
    taxis, core_repo: Path, claude_dir: Path, home: Path
) -> None:
    (core_repo / "core/tekton/persona/origin.md").write_text("uncommitted\n")
    assert taxis(*_brain(core_repo, "--worktree", "--yes"))[0] == 0
    assert "uncommitted" in (claude_dir / "CLAUDE.md").read_text()
    servers = {
        "local": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "local-mcp"],
            "env": {"CONFIG": f"{claude_dir}/mcp/pw.json"},
        },
        "remote": {"type": "http", "url": "https://mcp.example.com/mcp"},
        "bare": {"type": "stdio", "command": "bare-mcp", "args": []},
    }
    (claude_dir / ".claude.json").write_text(json.dumps({"mcpServers": servers}))
    code, out, _ = taxis(*_brain(core_repo, "--worktree"))
    flat = " ".join(out.split())
    assert (code, "already holds the core" in flat, "17 faithful" in flat) == (0, True, True)


def test_brain_unreadable_core_exits_13(taxis, tmp_path: Path) -> None:
    code, _, err = taxis(*_brain(tmp_path / "nowhere"))
    assert (code, "git archive" in err) == (13, True)


def test_brain_target_without_projection_exits_14(taxis, core_repo: Path) -> None:
    code, _, err = taxis("brain", "--target", "opencode", "--nous", str(core_repo))
    assert (code, "no brain projection" in err) == (14, True)


def test_install_without_yes_prints_both_plans(taxis, on_world, core_repo: Path, claude_dir: Path) -> None:
    code, out, _ = taxis("install", "--target", "claudecode", "--nous", str(core_repo), "--profile", "house")
    assert code == 0
    assert all(word in out for word in ("CLAUDE.md", "tool", "gated", "blocked"))
    assert not claude_dir.exists()


def test_install_lands_brain_then_systems_in_one_undoable_run(
    taxis, on_world, core_repo: Path, runner, claude_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATED_TOKEN", "set")
    install = ("install", "--target", "claudecode", "--nous", str(core_repo), "--profile", "house", *OPEN)
    code, out, _ = taxis(*install, "--yes")
    assert (code, "applied" in out) == (0, True)
    assert json.loads((claude_dir / "settings.json").read_text())["env"] == {"TOOL_ON": "1"}
    assert (claude_dir / "skills/demo/SKILL.md").is_file()
    assert [entry.split()[2] for entry in taxis("history", "list")[1].splitlines()[1:]] == ["install"]
    assert taxis("history", "undo")[0] == 0
    assert not claude_dir.exists()


def test_install_systems_failure_still_undoes_the_brain(taxis, on_world, core_repo: Path, claude_dir: Path) -> None:
    install = ("install", "--target", "claudecode", "--nous", str(core_repo), "--profile", "flaky", "--yes")
    code, _, err = taxis(*install)
    assert (code, "flaky" in err) == (10, True)
    assert (claude_dir / "CLAUDE.md").is_file()
    assert taxis("history", "undo")[0] == 0
    assert not claude_dir.exists()


def test_install_systems_from_the_checkout_stack(taxis, on_world, core_repo: Path) -> None:
    code, out, _ = taxis("install", "--target", "claudecode", "--nous", str(core_repo))
    assert (code, "nothing wanted for this target" in out) == (0, True)
