"""tests/unit/e_taxis/adapters/primitives/mcp: `claude mcp add-json`, stdio or http, reversed by `claude mcp remove`."""

import msgspec
import pytest

from e_taxis.harness.models.error import RecipeError
from e_taxis.harness.models.ports import PrimitivePort

REMOVE = ("claude", "mcp", "remove", "srv")


async def test_mcp_satisfies_the_port(mcp) -> None:
    assert isinstance(mcp, PrimitivePort)


@pytest.mark.parametrize(
    ("with_", "config"),
    [
        (
            {"name": "srv", "command": "~/.local/bin/srv", "args": ["--x"], "env": {"K": "V"}},
            {"type": "stdio", "command": "{home}/.local/bin/srv", "args": ["--x"], "env": {"K": "V"}},
        ),
        (
            {"name": "srv", "command": "npx", "args": ["-y", "p@1"]},
            {"type": "stdio", "command": "npx", "args": ["-y", "p@1"]},
        ),
        ({"name": "srv", "transport": "http", "url": "https://m/mcp"}, {"type": "http", "url": "https://m/mcp"}),
    ],
    ids=["stdio-home", "stdio-env-less", "http"],
)
async def test_mcp_install(mcp, entry, ctx, runner, home, with_, config) -> None:
    part = entry("claude-mcp", with_)
    step = await mcp.install(part, part.recipe(ctx.target), ctx)
    *argv, sent = runner.calls[0]
    assert argv == ["claude", "mcp", "add-json", "--scope", "user", "srv"]
    assert msgspec.json.decode(sent) == msgspec.json.decode(
        msgspec.json.encode(config).replace(b"{home}", str(home).encode())
    )
    assert step.effects[0].undo == REMOVE


async def test_mcp_update_removes_before_adding(mcp, entry, ctx, runner) -> None:
    part = entry("claude-mcp", {"name": "srv", "command": "srv"})
    step = await mcp.install(part, part.recipe(ctx.target), msgspec.structs.replace(ctx, update=True))
    assert [call[:3] for call in runner.calls] == [("claude", "mcp", "remove"), ("claude", "mcp", "add-json")]
    assert len(step.effects) == 1


@pytest.mark.parametrize(
    "with_", [{"name": "srv"}, {"name": "srv", "transport": "http"}], ids=["stdio-no-command", "http-no-url"]
)
async def test_mcp_install_incomplete_recipe_is_refused(mcp, entry, ctx, runner, with_) -> None:
    part = entry("claude-mcp", with_)
    with pytest.raises(RecipeError, match="stdio needs `command`, http needs `url`"):
        await mcp.install(part, part.recipe(ctx.target), ctx)
    assert runner.calls == []


async def test_mcp_uninstall_and_its_undo(mcp, entry, ctx, runner, undo) -> None:
    part = entry("claude-mcp", {"name": "srv", "command": "srv"}, uninstall={"name": "srv", "remove": True})
    step = await mcp.uninstall(part, part.uninstall, ctx)
    await undo(*step.effects)
    assert runner.calls == [
        REMOVE,
        ("claude", "mcp", "add-json", "--scope", "user", "srv", '{"type":"stdio","command":"srv","args":[]}'),
    ]
