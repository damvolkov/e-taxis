"""tests/unit/e_taxis/adapters/primitives/plugin: marketplace add, then plugin install — each reversed on undo."""

import pytest

from e_taxis.harness.models.error import RunnerError
from e_taxis.harness.models.journal import JournalCommand
from e_taxis.harness.models.ports import PrimitivePort

ADD = ("claude", "plugin", "marketplace", "add", "owner/repo")
DROP = ("claude", "plugin", "marketplace", "remove", "shop")
INSTALL = ("claude", "plugin", "install", "tool@shop")
UNINSTALL = ("claude", "plugin", "uninstall", "tool@shop")
WITH = {"source": "owner/repo", "name": "tool", "marketplace": "shop"}


async def test_plugin_satisfies_the_port(plugin) -> None:
    assert isinstance(plugin, PrimitivePort)


async def test_plugin_install_and_its_undo(plugin, entry, ctx, runner, undo) -> None:
    part = entry("claude-plugin", WITH)
    step = await plugin.install(part, part.recipe(ctx.target), ctx)
    assert step.effects == (JournalCommand(argv=ADD, undo=DROP), JournalCommand(argv=INSTALL, undo=UNINSTALL))
    await undo(*step.effects)
    assert runner.calls == [ADD, INSTALL, UNINSTALL, DROP]


async def test_plugin_install_failure_keeps_the_marketplace_for_undo(plugin, entry, ctx, runner) -> None:
    runner.failing.add(INSTALL)
    part = entry("claude-plugin", WITH)
    with pytest.raises(RunnerError) as failure:
        await plugin.install(part, part.recipe(ctx.target), ctx)
    assert failure.value.effects == (JournalCommand(argv=ADD, undo=DROP),)


async def test_plugin_uninstall_and_its_undo(plugin, entry, ctx, runner, undo) -> None:
    part = entry("claude-plugin", WITH, uninstall={"name": "tool", "marketplace": "shop"})
    await undo(*(await plugin.uninstall(part, part.uninstall, ctx)).effects)
    assert runner.calls == [UNINSTALL, INSTALL]
