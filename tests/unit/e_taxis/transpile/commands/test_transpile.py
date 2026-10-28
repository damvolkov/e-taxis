"""tests/unit/e_taxis/transpile/commands/transpile: `taxis transpile check` — clean exits 0, a break exits 20, JSON parses."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import anyio
import msgspec

from e_taxis.harness.runtime.deps import Deps
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.ports import CapturePort
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


def test_transpile_check_clean_checkout_exits_zero(taxis, nous_root: Path) -> None:
    code, out, _ = taxis("transpile", "check", "--nous", str(nous_root), "--worktree")
    assert code == 0
    assert out.rstrip().endswith("2 signal")


def test_transpile_check_blocking_finding_exits_twenty(
    taxis, nous_root: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit("specs/nomos/hermes.yaml", lambda s: s["map"]["config"]["unmapped"].pop("tools.calls"))
    code, out, err = taxis("transpile", "check", "--nous", str(nous_root), "--worktree")
    assert code == 20
    assert "tools.calls" in out
    assert "1 blocking finding" in err


def test_transpile_check_json_is_the_report(taxis, nous_git: Path) -> None:
    code, out, _ = taxis("transpile", "check", "--nous", str(nous_git), "--json")
    report = msgspec.json.decode(out)
    assert code == 0
    assert report["stamp"]["model"] == "2.0"
    assert len(report["stamp"]["commit"]) == 40


def test_transpile_run_exports_into_out(taxis, nous_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "export"
    code, stdout, _ = taxis(
        "transpile", "run", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--out", str(out)
    )
    assert code == 0
    assert "opencode →" in stdout
    assert (out / "AGENTS.md").is_file()


def test_transpile_run_json_lists_files_and_registry(taxis, nous_root: Path, tmp_path: Path) -> None:
    args = (
        "transpile",
        "run",
        "--target",
        "claudecode",
        "--nous",
        str(nous_root),
        "--worktree",
        "--out",
        str(tmp_path / "x"),
        "--json",
    )
    code, stdout, _ = taxis(*args)
    summary = msgspec.json.decode(stdout)
    assert code == 0
    assert "CLAUDE.md" in summary["files"]
    assert "e-gnosis" in summary["registry"]["mcp-user"]


def test_transpile_run_check_fails_while_the_live_tree_is_apart(taxis, nous_root: Path, tmp_path: Path) -> None:
    home = tmp_path / "live"
    args = ("transpile", "run", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--home", str(home))
    code, _, err = taxis(*args, "--check")
    assert code == 32
    assert "apart from the render" in " ".join(err.split())
    assert taxis(*args, "--yes", "--check")[0] == 0
    assert taxis(*args, "--check")[0] == 0


def test_transpile_run_without_out_plans_then_lands_with_yes(taxis, nous_root: Path, tmp_path: Path) -> None:
    home = tmp_path / "live"
    code, out, _ = taxis(
        "transpile", "run", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--home", str(home)
    )
    assert code == 0
    assert "plan only" in out
    assert not home.exists()
    code, out, _ = taxis(
        "transpile", "run", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--home", str(home), "--yes"
    )
    assert code == 0
    assert "landed opencode" in out
    assert (home / ".config/opencode/AGENTS.md").is_file()
    code, out, _ = taxis(
        "transpile",
        "run",
        "--target",
        "opencode",
        "--nous",
        str(nous_root),
        "--worktree",
        "--home",
        str(home),
        "--json",
    )
    assert msgspec.json.decode(out)["findings"] == []


def test_transpile_trial_reports_and_fails_when_not_held(
    taxis, nous_root: Path, fence, capture, hooked, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_trial(deps: Deps) -> TrialService:
        return TrialService(RunService(CheckService()), fence, path="/usr/bin")

    async def fake_capture(deps: Deps) -> CapturePort:
        return capture

    monkeypatch.setattr(
        Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, TrialService: fake_trial, CapturePort: fake_capture})
    )
    code, out, err = taxis("transpile", "trial", "--target", "claudecode", "--nous", str(nous_root), "--worktree")
    assert code == 22
    assert "NOT held" in out
    assert "did not show" in err
    code, out, _ = taxis(
        "transpile", "trial", "--target", "claudecode", "--nous", str(nous_root), "--worktree", "--json"
    )
    assert code == 22
    assert msgspec.json.decode(out)["backend"] == "claudecode"
    tree = anyio.run(GitNous(nous_root, None).load)
    slots = [*tree.persona["base"]["slots"].values(), *tree.persona["tekton"]["slots"].values()]
    fence.body = msgspec.json.encode([*slots, *tree.entities["skill"], *tree.entities["agent"]])
    fence.printer = hooked("claudecode", ".claude")
    code, out, _ = taxis("transpile", "trial", "--target", "claudecode", "--nous", str(nous_root), "--worktree")
    assert code == 0
    assert "· held" in out


def test_transpile_reverse_reports_after_a_landing(taxis, nous_root: Path, tmp_path: Path) -> None:
    home = tmp_path / "live"
    taxis(
        "transpile", "run", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--home", str(home), "--yes"
    )
    agents = home / ".config/opencode/AGENTS.md"
    agents.write_text(agents.read_text() + "\n\n## Mine\n\nmine")
    code, out, _ = taxis(
        "transpile", "reverse", "--target", "opencode", "--nous", str(nous_root), "--worktree", "--home", str(home)
    )
    assert code == 0
    assert "1 harness" in out
    code, out, _ = taxis(
        "transpile",
        "reverse",
        "--target",
        "opencode",
        "--nous",
        str(nous_root),
        "--worktree",
        "--home",
        str(home),
        "--json",
    )
    assert [finding["path"] for finding in msgspec.json.decode(out)["findings"]] == ["AGENTS.md#Mine"]
