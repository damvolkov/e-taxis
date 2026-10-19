"""tests/unit/e_taxis/adapters/primitives/settings: JSON merge of owned keys only — atomic, JSONC refused, undone key by key."""

import json
from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.ports import PrimitivePort
from e_taxis.models.error import JsoncError, OwnsError, RecipeError, SettingsError
from e_taxis.models.journal import JournalKey

if TYPE_CHECKING:
    from pathlib import Path

ENV = {"file": "~/.claude/settings.json", "env": {"A": "1", "B": "2"}}
OWNS = ("env.A", "env.B")
MCP = {"file": "~/.config/opencode/opencode.json", "key": "mcp.srv", "value": {"type": "local", "command": ["srv"]}}


async def test_settings_satisfies_the_port(settings) -> None:
    assert isinstance(settings, PrimitivePort)


async def test_settings_env_into_a_missing_file(settings, entry, ctx, claude_dir: Path) -> None:
    part = entry("settings", ENV, owns=OWNS)
    step = await settings.install(part, part.recipe(ctx.target), ctx)
    file = claude_dir / "settings.json"
    assert file.read_text() == '{\n  "env": {\n    "A": "1",\n    "B": "2"\n  }\n}\n'
    assert step.effects == (
        JournalKey(file=str(file), path=("env", "A"), created=2, fresh=True),
        JournalKey(file=str(file), path=("env", "B"), created=1),
    )


async def test_settings_key_merge_keeps_every_other_key(settings, entry, ctx, home: Path) -> None:
    file = home / ".config/opencode/opencode.json"
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({"theme": "x", "mcp": {"other": {"type": "remote"}, "srv": "old"}}))
    part = entry("settings", MCP, owns=("mcp.srv",))
    step = await settings.install(part, part.recipe(ctx.target), ctx)
    assert json.loads(file.read_text()) == {"theme": "x", "mcp": {"other": {"type": "remote"}, "srv": MCP["value"]}}
    assert step.effects == (JournalKey(file=str(file), path=("mcp", "srv"), before="old"),)


async def test_settings_unchanged_writes_nothing(settings, entry, ctx, claude_dir: Path) -> None:
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"env": {"A": "1", "B": "2"}}')
    part = entry("settings", ENV, owns=OWNS)
    assert (await settings.install(part, part.recipe(ctx.target), ctx)).effects == ()
    assert (claude_dir / "settings.json").read_text() == '{"env": {"A": "1", "B": "2"}}'


async def test_settings_owns_violation_is_refused(settings, entry, ctx, claude_dir: Path) -> None:
    part = entry("settings", ENV, owns=("env.A",))
    with pytest.raises(OwnsError, match=r"env\.B"):
        await settings.install(part, part.recipe(ctx.target), ctx)
    assert not (claude_dir / "settings.json").exists()


@pytest.mark.parametrize(
    ("text", "error", "match"),
    [
        ('{\n  // telemetry\n  "env": {}\n}', JsoncError, "not plain JSON"),
        ('{"env": {},}', JsoncError, "not plain JSON"),
        ("[1, 2]", SettingsError, "root is not a JSON object"),
        ('{"env": "flat"}', SettingsError, "env is not a JSON object"),
    ],
    ids=["comment", "trailing-comma", "root-array", "parent-scalar"],
)
async def test_settings_unmergeable_file_is_refused(
    settings, entry, ctx, claude_dir: Path, text: str, error: type[Exception], match: str
) -> None:
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(text)
    part = entry("settings", ENV, owns=OWNS)
    with pytest.raises(error, match=match):
        await settings.install(part, part.recipe(ctx.target), ctx)
    assert (claude_dir / "settings.json").read_text() == text


@pytest.mark.parametrize(
    "with_", [{"file": "f.json"}, {"file": "f.json", "env": {}, "key": "a"}], ids=["neither", "both"]
)
async def test_settings_recipe_needs_env_or_key(settings, entry, ctx, with_) -> None:
    part = entry("settings", with_)
    with pytest.raises(RecipeError, match="exactly one"):
        await settings.install(part, part.recipe(ctx.target), ctx)


async def test_settings_undo_of_a_fresh_file_removes_it(settings, entry, ctx, undo, claude_dir: Path) -> None:
    part = entry("settings", ENV, owns=OWNS)
    await undo(*(await settings.install(part, part.recipe(ctx.target), ctx)).effects)
    assert not (claude_dir / "settings.json").exists()


async def test_settings_undo_restores_prior_values_and_drops_created_keys(
    settings, entry, ctx, undo, claude_dir: Path
) -> None:
    claude_dir.mkdir()
    prior = {"model": "x", "env": {"A": "0"}}
    (claude_dir / "settings.json").write_text(json.dumps(prior))
    part = entry("settings", ENV, owns=OWNS)
    await undo(*(await settings.install(part, part.recipe(ctx.target), ctx)).effects)
    assert json.loads((claude_dir / "settings.json").read_text()) == prior


async def test_settings_undo_keeps_keys_others_added_since(settings, entry, ctx, undo, claude_dir: Path) -> None:
    part = entry("settings", ENV, owns=OWNS)
    effects = (await settings.install(part, part.recipe(ctx.target), ctx)).effects
    (claude_dir / "settings.json").write_text(json.dumps({"env": {"A": "1", "B": "2"}, "model": "y"}))
    await undo(*effects)
    assert json.loads((claude_dir / "settings.json").read_text()) == {"model": "y"}


async def test_settings_undo_of_a_vanished_file_writes_nothing(settings, entry, ctx, undo, claude_dir: Path) -> None:
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    part = entry("settings", ENV, owns=OWNS)
    effects = (await settings.install(part, part.recipe(ctx.target), ctx)).effects
    (claude_dir / "settings.json").unlink()
    await undo(*effects)
    assert not (claude_dir / "settings.json").exists()


async def test_settings_uninstall_drops_owned_keys_and_its_undo(settings, entry, ctx, undo, claude_dir: Path) -> None:
    claude_dir.mkdir()
    prior = {"env": {"A": "1", "B": "2", "KEEP": "x"}}
    (claude_dir / "settings.json").write_text(json.dumps(prior))
    part = entry("settings", ENV, owns=(*OWNS, "env.C"), uninstall={"file": "~/.claude/settings.json"})
    step = await settings.uninstall(part, part.uninstall, ctx)
    assert json.loads((claude_dir / "settings.json").read_text()) == {"env": {"KEEP": "x"}}
    await undo(*step.effects)
    assert json.loads((claude_dir / "settings.json").read_text()) == prior


async def test_settings_uninstall_of_a_missing_file_changes_nothing(settings, entry, ctx, claude_dir: Path) -> None:
    part = entry("settings", ENV, owns=OWNS, uninstall={"file": "~/.claude/settings.json"})
    assert (await settings.uninstall(part, part.uninstall, ctx)).effects == ()
    assert not (claude_dir / "settings.json").exists()
