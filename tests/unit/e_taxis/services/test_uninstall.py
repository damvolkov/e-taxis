"""tests/unit/e_taxis/services/uninstall: one part, or with --cascade its dependents first — probed, planned or removed
through the entry's uninstall recipe, fail-fast, every change recorded for undo."""

import json
from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.models.catalog import Primitive, Target
from e_taxis.models.error import CatalogCycleError, UninstallError
from e_taxis.models.journal import JournalKey
from e_taxis.models.uninstall import UninstallStatus
from e_taxis.services.resolver import ResolverService
from e_taxis.services.uninstall import UninstallService

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def installed(home: Path, claude_dir: Path) -> None:
    """tool, env and guide present in the temp HOME, gated absent."""
    (home / ".tool").touch()
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"env": {"TOOL_ON": "1"}, "model": "x"}))
    (claude_dir / "CLAUDE.md").write_text("<!-- e-taxis:guide -->\nUse the tool.\n<!-- /e-taxis:guide -->\n")


async def test_uninstall_unknown_part_is_refused(uninstaller: UninstallService) -> None:
    with pytest.raises(UninstallError, match="no entry nope serves claudecode"):
        await uninstaller.run("nope", Target.CLAUDECODE, cascade=False, write=True)


async def test_uninstall_dry_run_plans_without_writing(uninstaller: UninstallService, installed, runner) -> None:
    report = await uninstaller.run("tool", Target.CLAUDECODE, cascade=False, write=False)
    assert ([step.status for step in report.steps], runner.calls) == ([UninstallStatus.PLANNED], [])


async def test_uninstall_absent_part_is_left_alone(uninstaller: UninstallService, runner) -> None:
    report = await uninstaller.run("tool", Target.CLAUDECODE, cascade=False, write=True)
    assert ([step.status for step in report.steps], runner.calls) == ([UninstallStatus.ABSENT], [])


async def test_uninstall_removes_through_the_recipe_and_records(
    uninstaller: UninstallService, installed, recorder, claude_dir: Path
) -> None:
    report = await uninstaller.run("env", Target.CLAUDECODE, cascade=False, write=True)
    assert [step.status for step in report.steps] == [UninstallStatus.REMOVED]
    assert json.loads((claude_dir / "settings.json").read_text()) == {"env": {}, "model": "x"}
    assert recorder.effects == [JournalKey(file=str(claude_dir / "settings.json"), path=("env", "TOOL_ON"), before="1")]


async def test_uninstall_cascade_removes_dependents_first(
    uninstaller: UninstallService, installed, runner, claude_dir: Path
) -> None:
    report = await uninstaller.run("tool", Target.CLAUDECODE, cascade=True, write=True)
    statuses = [(step.id, step.status) for step in report.steps]
    assert statuses[-1] == ("tool", UninstallStatus.REMOVED)
    assert statuses.index(("guide", UninstallStatus.REMOVED)) < statuses.index(("env", UninstallStatus.REMOVED))
    assert ("gated", UninstallStatus.ABSENT) in statuses
    assert runner.calls == [("uv", "tool", "uninstall", "tool")]
    assert not (claude_dir / "CLAUDE.md").exists() or "e-taxis:guide" not in (claude_dir / "CLAUDE.md").read_text()


async def test_uninstall_cascade_stops_at_the_first_failure(
    uninstaller: UninstallService, installed, runner, home: Path
) -> None:
    (home / ".gated").touch()
    runner.failing.add(("claude",))
    report = await uninstaller.run("tool", Target.CLAUDECODE, cascade=True, write=True)
    statuses = {step.id: step.status for step in report.steps}
    assert (statuses["gated"], statuses["tool"], report.failed) == (
        UninstallStatus.FAILED,
        UninstallStatus.NOT_RUN,
        ("gated",),
    )


async def test_uninstall_without_a_recipe_fails(uninstaller: UninstallService) -> None:
    report = await uninstaller.run("here", Target.CLAUDECODE, cascade=False, write=True)
    assert (report.steps[0].status, report.steps[0].detail) == (UninstallStatus.FAILED, "no uninstall recipe")


async def test_uninstall_recipe_for_another_primitive_fails(uninstaller: UninstallService) -> None:
    report = await uninstaller.run("split", Target.OPENCODE, cascade=False, write=True)
    assert report.steps[0].status is UninstallStatus.FAILED
    assert "uninstall recipe is claude-mcp, opencode installs through settings" in report.steps[0].detail


async def test_uninstall_p3_parts_are_deferred(uninstaller: UninstallService, home: Path) -> None:
    (home / ".svc").touch()
    report = await uninstaller.run("svc", Target.CLAUDECODE, cascade=False, write=True)
    assert report.steps[0].status is UninstallStatus.DEFERRED


async def test_uninstall_a_primitive_not_supported_yet_is_deferred(
    uninstaller: UninstallService, primitives, installed
) -> None:
    primitives[Primitive.UV_TOOL] = ComposePrimitive()
    report = await uninstaller.run("tool", Target.CLAUDECODE, cascade=False, write=True)
    assert report.steps[0].status is UninstallStatus.DEFERRED


async def test_uninstall_cascade_over_a_cycle_is_refused(cycle_root: Path, probe, primitives, recorder, home) -> None:
    service = UninstallService(
        ResolverService(FileCatalog(cycle_root)), probe, primitives, recorder, home=home, claude=home / ".claude"
    )
    with pytest.raises(CatalogCycleError):
        await service.run("a", Target.CLAUDECODE, cascade=True, write=False)
