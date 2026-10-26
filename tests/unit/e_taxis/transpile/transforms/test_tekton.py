"""tests/unit/e_taxis/transpile/transforms/tekton: each backend's table equals its spec's contracts, and each holds."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.transforms import claudecode, opencode
from e_taxis.transpile.transforms.catalog import CATALOG

if TYPE_CHECKING:
    from e_taxis.transpile.engine.context import RowContext
    from e_taxis.transpile.models.nous import NousTree


@pytest.mark.parametrize("backend", ["claudecode", "opencode"])
async def test_tekton_table_equals_the_spec(nous_tree: NousTree, backend: str) -> None:
    assert set(CATALOG[backend]) == set(nous_tree.specs[f"tekton/{backend}"]["transforms"])


async def test_tekton_telemetry_names_each_signal(ctx: RowContext) -> None:
    env = claudecode.claude_telemetry({"endpoint": "http://c", "protocol": "grpc", "signals": ["logs"]}, ctx)
    assert env == {
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        "OTEL_LOGS_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://c",
    }


async def test_tekton_hooks_one_entry_per_matcher_none_without(ctx: RowContext) -> None:
    hooks: dict[str, list[dict[str, Any]]] = {
        "Start": [{"matchers": ["a", "b"], "run": ["node", "{out}/x y"]}],
        "Stop": [{"run": ["bash"]}],
    }
    assert claudecode.claude_hooks(hooks, ctx) == {
        "Start": [
            {"matcher": "a", "hooks": [{"type": "command", "command": "node '/out/x y'"}]},
            {"matcher": "b", "hooks": [{"type": "command", "command": "node '/out/x y'"}]},
        ],
        "Stop": [{"hooks": [{"type": "command", "command": "bash"}]}],
    }


@pytest.mark.parametrize(
    ("entries", "claude", "code"),
    [(["{out}/a", {"path": "{out}/b", "backends": ["opencode"]}], "@/out/a\n", ["/out/a", "/out/b"])],
)
async def test_tekton_instructions_reach_by_backend(
    ctx: RowContext, entries: list[Any], claude: str, code: list[str]
) -> None:
    assert claudecode.at_imports(entries, ctx) == claude
    assert opencode.instructions_opencode(entries, ctx) == code


@pytest.mark.parametrize(
    ("server", "expected"),
    [
        (
            {"command": ["npx", "{out}/a"], "env": {"K": "{out}"}},
            {"type": "stdio", "command": "npx", "args": ["/out/a"], "env": {"K": "/out"}},
        ),
        ({"command": ["bin"]}, {"type": "stdio", "command": "bin", "args": []}),
        ({"url": "http://u"}, {"type": "http", "url": "http://u"}),
        ({"url": "http://u", "backends": ["opencode"]}, None),
    ],
    ids=["stdio", "bare", "http", "elsewhere"],
)
async def test_tekton_mcp_claudecode(ctx: RowContext, server: dict[str, Any], expected: Any) -> None:
    assert claudecode.mcp_claudecode(server, ctx) == expected


async def test_tekton_mcp_opencode_keeps_its_servers(ctx: RowContext) -> None:
    servers = {
        "l": {"command": ["x", "{out}"], "env": {"A": "1"}},
        "r": {"url": "http://u"},
        "c": {"url": "http://c", "backends": ["claudecode"]},
    }
    assert opencode.mcp_opencode(servers, ctx) == {
        "l": {"type": "local", "command": ["x", "/out"], "environment": {"A": "1"}, "enabled": True},
        "r": {"type": "remote", "url": "http://u", "enabled": True},
    }


async def test_tekton_agents_registry_resolves_tiers(ctx: RowContext) -> None:
    agents = {"overrides": {"plan": {"model": "scout"}}, "system": {"x": {"hidden": True}}}
    assert opencode.agents_registry(agents, ctx) == {
        "plan": {"model": "bailian-token-plan-personal/qwen3.6-flash"},
        "x": {"hidden": True},
    }


async def test_tekton_agents_registry_refuses_a_name_in_both(ctx: RowContext) -> None:
    with pytest.raises(RenderError, match="both"):
        opencode.agents_registry({"overrides": {"x": {}}, "system": {"x": {}}}, ctx)


async def test_tekton_providers_tree_and_dependency(ctx: RowContext) -> None:
    tree = opencode.providers_tree(ctx.config["models"], ctx)
    provider = tree["bailian-token-plan-personal"]
    assert next(iter(provider["models"])) == "qwen3.8-max"
    assert provider["models"]["qwen3.8-max"]["name"] == "builder"
    assert opencode.npm_dependency("@scope/pkg@1.2", ctx) == {"@scope/pkg": "1.2"}
