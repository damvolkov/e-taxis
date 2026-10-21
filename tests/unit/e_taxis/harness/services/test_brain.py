"""tests/unit/e_taxis/services/brain: the core installed into the temp Claude tree — a three-way plan, every change
recorded the moment it lands, the record of what landed, registrations through the CLI, nothing ever deleted."""

import hashlib
import json
from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.adapters.core import GitCore
from e_taxis.adapters.harness.claudecode import ClaudecodeHarness
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.harness.models.brain import BrainAction
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import BrainError
from e_taxis.harness.models.journal import JournalCommand, JournalFile, JournalKey
from e_taxis.harness.services.brain import BrainService

if TYPE_CHECKING:
    from pathlib import Path

ADD_REMOTE = ("claude", "mcp", "add-json", "--scope", "user", "remote")


@pytest.fixture
def core(core_root: Path) -> GitCore:
    return GitCore(core_root, None)


@pytest.fixture
def brain(runner, store, recorder, claude_dir: Path) -> BrainService:
    harnesses = {Target.CLAUDECODE: ClaudecodeHarness()}
    registry = claude_dir / ".claude.json"
    return BrainService(harnesses, SettingsPrimitive(), runner, store, recorder, claude=claude_dir, registry=registry)


def _actions(plan) -> dict[str, BrainAction]:
    return {move.path: move.action for move in plan.moves}


async def test_brain_plan_on_an_empty_tree_adds_everything(brain: BrainService, core, claude_dir: Path) -> None:
    plan = await brain.plan(core, Target.CLAUDECODE)
    assert set(_actions(plan).values()) == {BrainAction.ADD}
    assert "settings.json#hooks" in _actions(plan)
    assert "mcp:local" in _actions(plan)
    assert (plan.tree, claude_dir.exists()) == (str(claude_dir), False)


async def test_brain_run_lands_records_and_then_holds_faithful(
    brain: BrainService, core, runner, recorder, store, claude_dir: Path
) -> None:
    plan = await brain.run(core, Target.CLAUDECODE)
    assert len(plan.pending) == len(plan.moves)
    assert (claude_dir / "skills/demo/references/a.md").read_text() == "Reference A.\n"
    assert json.loads((claude_dir / "settings.json").read_text())["model"] == "opus"
    assert [call[:6] for call in runner.calls] == [
        ("claude", "mcp", "add-json", "--scope", "user", "local"),
        ADD_REMOTE,
        ("claude", "mcp", "add-json", "--scope", "user", "bare"),
    ]
    kinds = [type(effect) for effect in recorder.effects]
    assert kinds == [JournalFile] * 8 + [JournalKey] * 6 + [JournalCommand] * 3
    assert all(effect.before is None for effect in recorder.effects if isinstance(effect, JournalFile))
    record = msgspec.json.decode(store.data["brain:claudecode"])
    assert record["CLAUDE.md"] == hashlib.sha256((claude_dir / "CLAUDE.md").read_bytes()).hexdigest()
    assert len(record) == 8
    ### the registrations land in ~/.claude.json, which the fake runner does not write: they stay `add`.
    again = await brain.plan(core, Target.CLAUDECODE)
    assert {path for path, action in _actions(again).items() if action is not BrainAction.FAITHFUL} == {
        "mcp:local",
        "mcp:remote",
        "mcp:bare",
    }


async def test_brain_plan_tells_update_from_overwrite(brain: BrainService, core, store, claude_dir: Path) -> None:
    await brain.run(core, Target.CLAUDECODE)
    (claude_dir / "agents/scout.md").write_text("edited by hand\n")
    ### a file the last install wrote, then the core moved: the tree and the record hold the old render.
    (claude_dir / "commands/ask.md").write_text("old render\n")
    landed = msgspec.json.decode(store.data["brain:claudecode"], type=dict[str, str])
    landed["commands/ask.md"] = hashlib.sha256(b"old render\n").hexdigest()
    store.data["brain:claudecode"] = msgspec.json.encode(landed)
    actions = _actions(await brain.plan(core, Target.CLAUDECODE))
    assert (actions["agents/scout.md"], actions["commands/ask.md"]) == (BrainAction.OVERWRITE, BrainAction.UPDATE)


async def test_brain_keys_keep_every_key_the_harness_wrote(brain: BrainService, core, claude_dir: Path) -> None:
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"statusLine": {"type": "command"}, "model": "sonnet"}\n')
    actions = _actions(await brain.plan(core, Target.CLAUDECODE))
    assert (actions["settings.json#model"], actions["settings.json#tui"]) == (BrainAction.UPDATE, BrainAction.ADD)
    await brain.run(core, Target.CLAUDECODE)
    settings = json.loads((claude_dir / "settings.json").read_text())
    assert (settings["statusLine"], settings["model"]) == ({"type": "command"}, "opus")


async def test_brain_document_keeps_live_sections_and_orphans_stay(brain: BrainService, core, claude_dir: Path) -> None:
    (claude_dir / "skills/gone").mkdir(parents=True)
    (claude_dir / "skills/gone/SKILL.md").write_text("old skill\n")
    (claude_dir / "CLAUDE.md").write_text("# Old\n\n## Local notes\n\nmine\n")
    actions = _actions(await brain.plan(core, Target.CLAUDECODE))
    assert (actions["skills/gone"], actions["CLAUDE.md"]) == (BrainAction.ORPHAN, BrainAction.OVERWRITE)
    await brain.run(core, Target.CLAUDECODE)
    assert (claude_dir / "skills/gone/SKILL.md").read_text() == "old skill\n"
    assert (claude_dir / "CLAUDE.md").read_text().endswith("## Skills\n\nSkills.\n\n## Local notes\n\nmine")


async def test_brain_registration_update_records_how_to_put_the_old_one_back(
    brain: BrainService, core, runner, recorder, claude_dir: Path
) -> None:
    claude_dir.mkdir()
    old = {"type": "http", "url": "https://old.example.com"}
    (claude_dir / ".claude.json").write_text(json.dumps({"mcpServers": {"remote": old}}))
    assert _actions(await brain.plan(core, Target.CLAUDECODE))["mcp:remote"] is BrainAction.UPDATE
    await brain.run(core, Target.CLAUDECODE)
    commands = [effect for effect in recorder.effects if isinstance(effect, JournalCommand)]
    remove = ("claude", "mcp", "remove", "remote")
    assert (commands[1].argv, commands[1].undo[:6], json.loads(commands[1].undo[6])) == (remove, ADD_REMOTE, old)
    assert (commands[2].argv[:6], commands[2].undo) == (ADD_REMOTE, remove)
    assert remove in runner.calls


async def test_brain_target_without_a_projection_is_refused(brain: BrainService, core) -> None:
    with pytest.raises(BrainError, match="no brain projection for opencode"):
        await brain.plan(core, Target.OPENCODE)


async def test_brain_failure_keeps_what_landed_recorded(brain: BrainService, core, runner, recorder, store) -> None:
    runner.failing.add(ADD_REMOTE)
    with pytest.raises(BrainError, match="history undo"):
        await brain.run(core, Target.CLAUDECODE)
    assert sum(isinstance(effect, JournalFile) for effect in recorder.effects) == 8
    assert sum(isinstance(effect, JournalCommand) for effect in recorder.effects) == 1
    assert "brain:claudecode" not in store.data
