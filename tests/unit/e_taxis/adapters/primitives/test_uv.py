"""tests/unit/e_taxis/adapters/primitives/uv: `uv tool install <source>`, reversed by `uv tool uninstall <name>`."""

import pytest

from e_taxis.harness.models.error import RecipeError, RunnerError
from e_taxis.harness.models.journal import JournalCommand
from e_taxis.harness.models.ports import PrimitivePort

INSTALL = ("uv", "tool", "install", "git+https://x/tool@v1")
UNINSTALL = ("uv", "tool", "uninstall", "tool")


async def test_uv_satisfies_the_port(uv) -> None:
    assert isinstance(uv, PrimitivePort)


async def test_uv_install_and_its_undo(uv, entry, ctx, runner, undo) -> None:
    part = entry("uv-tool", {"source": "git+https://x/tool@v1", "name": "tool"})
    step = await uv.install(part, part.recipe(ctx.target), ctx)
    assert step.effects == (JournalCommand(argv=INSTALL, undo=UNINSTALL),)
    await undo(*step.effects)
    assert runner.calls == [INSTALL, UNINSTALL]


async def test_uv_uninstall_and_its_undo(uv, entry, ctx, runner, undo) -> None:
    part = entry("uv-tool", {"source": "git+https://x/tool@v1", "name": "tool"}, uninstall={"name": "tool"})
    await undo(*(await uv.uninstall(part, part.uninstall, ctx)).effects)
    assert runner.calls == [UNINSTALL, INSTALL]


async def test_uv_install_failure_changes_nothing(uv, entry, ctx, runner) -> None:
    runner.failing.add(("uv",))
    part = entry("uv-tool", {"source": "s", "name": "tool"})
    with pytest.raises(RunnerError) as failure:
        await uv.install(part, part.recipe(ctx.target), ctx)
    assert failure.value.effects == ()


async def test_uv_recipe_without_name_is_refused(uv, entry, ctx) -> None:
    part = entry("uv-tool", {"source": "s"})
    with pytest.raises(RecipeError, match="name"):
        await uv.install(part, part.recipe(ctx.target), ctx)
