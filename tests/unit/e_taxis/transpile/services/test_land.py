"""tests/unit/e_taxis/transpile/services/land: plan against a temp HOME, land through the journal, hold idempotence."""

from typing import TYPE_CHECKING

import msgspec

from e_taxis.harness.models.journal import JournalCommand, JournalFile
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.report import ReportKind
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import LandService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from pathlib import Path


def _lander(runner, store, recorder) -> LandService:
    return LandService(RunService(CheckService()), runner, store, recorder)


async def test_land_plan_on_an_empty_home_is_all_missing(
    nous_root: Path, tmp_path: Path, runner, store, recorder
) -> None:
    report = await _lander(runner, store, recorder).plan(GitNous(nous_root, None), "claudecode", tmp_path / "h")
    assert {finding.kind for finding in report.findings} == {ReportKind.MISSING}
    assert any(finding.path == "mcp-user#exa" for finding in report.findings)
    assert runner.calls == []


async def test_land_apply_writes_records_and_settles(nous_root: Path, tmp_path: Path, runner, store, recorder) -> None:
    home = tmp_path / "h"
    lander = _lander(runner, store, recorder)
    await lander.apply(GitNous(nous_root, None), "claudecode", home)
    assert (home / ".claude/CLAUDE.md").read_text().startswith("# Demian")
    assert msgspec.json.decode((home / ".claude/settings.json").read_bytes())["model"] == "opus[1m]"
    adds = [call for call in runner.calls if "add-json" in call]
    assert adds[0][:4] == ("env", "-u", "CLAUDE_CONFIG_DIR", f"HOME={home}")
    assert {type(effect) for effect in recorder.effects} == {JournalFile, JournalCommand}
    record = msgspec.json.decode(store.data["transpile:claudecode"])
    assert "settings.json" in record["files"]
    assert record["commit"] == "worktree"
    registry = {name.split("#")[1]: msgspec.json.decode(call[-1]) for call, name in [(c, f"x#{c[-2]}") for c in adds]}
    (home / ".claude.json").write_bytes(msgspec.json.encode({"mcpServers": registry}))
    again = await lander.plan(GitNous(nous_root, None), "claudecode", home)
    assert again.findings == ()


async def test_land_apply_prunes_replaces_and_resyncs(nous_root: Path, tmp_path: Path, runner, store, recorder) -> None:
    home = tmp_path / "h"
    tree = home / ".claude"
    lander = _lander(runner, store, recorder)
    await lander.apply(GitNous(nous_root, None), "claudecode", home)
    (tree / "hooks/old-hook").write_text("retired")
    (tree / "skills/synced").mkdir(parents=True)
    (tree / "skills/synced/keep.md").write_text("autolearn's")
    target = tmp_path / "elsewhere.md"
    target.write_text("linked")
    (tree / "CLAUDE.md").unlink()
    (tree / "CLAUDE.md").symlink_to(target)
    (home / ".claude.json").write_bytes(
        msgspec.json.encode({"mcpServers": {"exa": {"type": "http", "url": "http://old"}, "stray": {}}})
    )
    runner.calls.clear()
    report = await lander.apply(GitNous(nous_root, None), "claudecode", home)
    kinds = {(finding.kind, finding.path) for finding in report.findings}
    assert (ReportKind.STALE, "hooks/old-hook") in kinds
    assert (ReportKind.SYMLINK, "CLAUDE.md") in kinds
    assert (ReportKind.DRIFT, "mcp-user#exa") in kinds
    assert (ReportKind.STALE, "mcp-user#stray") in kinds
    assert not (tree / "hooks/old-hook").exists()
    assert (tree / "skills/synced/keep.md").is_file()
    assert not (tree / "CLAUDE.md").is_symlink()
    assert target.read_text() == "linked"
    removed = [call[-1] for call in runner.calls if "remove" in call]
    assert sorted(removed) == ["exa", "stray"]


async def test_land_registry_absent_file_reads_empty(nous_root: Path, tmp_path: Path, runner, store, recorder) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / ".claude.json").write_text("[]")
    report = await _lander(runner, store, recorder).plan(GitNous(nous_root, None), "claudecode", home)
    assert any(finding.path == "mcp-user#exa" and finding.kind is ReportKind.MISSING for finding in report.findings)


async def test_land_remove_of_a_vanished_file_is_quiet(tmp_path: Path, runner, store, recorder) -> None:
    await _lander(runner, store, recorder)._land_remove(tmp_path / "gone")
    assert recorder.effects == []
