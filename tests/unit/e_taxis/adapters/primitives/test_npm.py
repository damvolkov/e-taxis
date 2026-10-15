"""tests/unit/e_taxis/adapters/primitives/npm: `npm install -g <package@version>` into the configured prefix."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.ports import PrimitivePort
from e_taxis.adapters.primitives.npm import NpmPrimitive
from e_taxis.models.journal import JournalCommand

if TYPE_CHECKING:
    from pathlib import Path


async def test_npm_satisfies_the_port(npm) -> None:
    assert isinstance(npm, PrimitivePort)


@pytest.mark.parametrize(
    ("package", "name"),
    [("ccusage@20.0.33", "ccusage"), ("@scope/pkg@1.2", "@scope/pkg"), ("@scope/pkg", "@scope/pkg")],
)
async def test_npm_install_and_its_undo(npm, entry, ctx, runner, undo, package: str, name: str) -> None:
    part = entry("npm", {"package": package})
    step = await npm.install(part, part.recipe(ctx.target), ctx)
    assert step.effects == (
        JournalCommand(argv=("npm", "install", "-g", package), undo=("npm", "uninstall", "-g", name)),
    )
    await undo(*step.effects)
    assert runner.calls[-1] == ("npm", "uninstall", "-g", name)


async def test_npm_prefix_from_settings(entry, ctx, runner, tmp_path: Path) -> None:
    part = entry("npm", {"package": "ccusage@1"}, uninstall={"package": "ccusage"})
    await NpmPrimitive(runner, prefix=tmp_path).uninstall(part, part.uninstall, ctx)
    assert runner.calls == [("npm", "uninstall", "-g", "--prefix", str(tmp_path), "ccusage")]


async def test_npm_uninstall_undo_reinstalls_the_pin(npm, entry, ctx, runner, undo) -> None:
    part = entry("npm", {"package": "ccusage@1"}, uninstall={"package": "ccusage"})
    await undo(*(await npm.uninstall(part, part.uninstall, ctx)).effects)
    assert runner.calls == [("npm", "uninstall", "-g", "ccusage"), ("npm", "install", "-g", "ccusage@1")]
