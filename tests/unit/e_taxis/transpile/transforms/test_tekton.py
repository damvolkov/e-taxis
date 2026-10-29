"""tests/unit/e_taxis/transpile/transforms/tekton: each backend's table equals its spec's contracts, and each holds."""

from dataclasses import replace
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


async def test_tekton_hooks_claude_names_each_house_event(ctx: RowContext) -> None:
    hooks: dict[str, list[dict[str, Any]]] = {
        "session_start": [{"matchers": ["startup", "resume"], "run": ["node", "{out}/x y"]}],
        "tool_before": [{"matchers": ["edit", "bash"], "run": ["guard"]}, {"run": ["all"], "backends": ["opencode"]}],
        "turn_end": [{"run": ["bash"]}],
        "session_end": [{"run": ["far"], "backends": ["opencode"]}],
    }
    assert claudecode.claude_hooks(hooks, ctx) == {
        "SessionStart": [{"matcher": "startup|resume", "hooks": [{"type": "command", "command": "node '/out/x y'"}]}],
        "PreToolUse": [{"matcher": "Edit|Write|NotebookEdit|Bash", "hooks": [{"type": "command", "command": "guard"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "bash"}]}],
    }


@pytest.mark.parametrize(
    ("hooks", "match"),
    [
        ({"model_before": [{"run": ["x"]}]}, "`model_before` has no realization"),
        ({"tool_before": [{"matchers": ["todo"], "run": ["x"]}]}, "`todo` is a house tool"),
    ],
    ids=["event", "tool"],
)
async def test_tekton_hooks_refuse_what_claude_cannot_realize(
    ctx: RowContext, hooks: dict[str, Any], match: str
) -> None:
    with pytest.raises(RenderError, match=match):
        claudecode.claude_hooks(hooks, ctx)


async def test_tekton_hooks_opencode_binds_each_hook(nous_tree: NousTree, ctx: RowContext) -> None:
    native = nous_tree.specs["tekton/opencode"]["native"]
    hooks: dict[str, list[dict[str, Any]]] = {
        "session_start": [{"matchers": ["startup"], "run": ["a"]}, {"run": ["c"], "backends": ["claudecode"]}],
        "tool_after": [{"matchers": ["bash", "edit"], "run": ["b", "{out}"]}],
    }
    assert opencode.opencode_hooks(hooks, replace(ctx, native=native)) == [
        {
            "event": "session_start",
            "domain": "event",
            "name": "session.created",
            "when": {"parentID": None},
            "effect": "none",
            "matchers": [],
            "command": "a",
        },
        {
            "event": "tool_after",
            "domain": "tool",
            "name": "execute.after",
            "when": {"status": "completed"},
            "effect": "none",
            "matchers": ["shell", "edit", "write"],
            "command": "b /out",
        },
    ]


@pytest.mark.parametrize(
    ("hooks", "match"),
    [
        ({"session_start": [{"matchers": ["resume"], "run": ["x"]}]}, r"honours only \['startup'\], not \['resume'\]"),
        ({"turn_end": [{"matchers": ["any"], "run": ["x"]}]}, r"honours only \[\]"),
        ({"compact_before": [{"run": ["x"]}]}, "`compact_before` has no realization"),
        ({"tool_before": [{"matchers": ["lsp"], "run": ["x"]}]}, "`lsp` is a house tool"),
    ],
    ids=["origin", "none-admitted", "event", "tool"],
)
async def test_tekton_hooks_refuse_what_opencode_cannot_realize(
    nous_tree: NousTree, ctx: RowContext, hooks: dict[str, Any], match: str
) -> None:
    with pytest.raises(RenderError, match=match):
        opencode.opencode_hooks(hooks, replace(ctx, native=nous_tree.specs["tekton/opencode"]["native"]))


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


async def test_tekton_mcp_opencode_speaks_its_env_syntax(ctx: RowContext) -> None:
    servers = {
        "r": {"url": "http://u", "headers": {"Authorization": "Bearer ${KB_TOKEN}"}},
        "l": {"command": ["x"], "env": {"K": "${KEY}-${KEY2}", "P": "plain"}},
    }
    assert opencode.mcp_opencode(servers, ctx) == {
        "r": {
            "type": "remote",
            "url": "http://u",
            "headers": {"Authorization": "Bearer {env:KB_TOKEN}"},
            "enabled": True,
        },
        "l": {
            "type": "local",
            "command": ["x"],
            "environment": {"K": "{env:KEY}-{env:KEY2}", "P": "plain"},
            "enabled": True,
        },
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


async def test_tekton_providers_tree_shares_one_model_across_tiers(ctx: RowContext) -> None:
    think = {"thinking": {"type": "enabled", "budgetTokens": 4096}}
    tiers = {"builder": {"model": "bailian/m", "options": think}, "scout": {"model": "bailian/m", "options": think}}
    tree = opencode.providers_tree(ctx.config["models"] | {"tiers": tiers}, ctx)
    assert tree["bailian-token-plan-personal"]["models"] == {"m": {"name": "builder/scout", "options": think}}


async def test_tekton_providers_tree_refuses_tiers_disagreeing_on_a_model(ctx: RowContext) -> None:
    tiers = {"builder": {"model": "bailian/m", "reasoning": True}, "scout": {"model": "bailian/m"}}
    with pytest.raises(RenderError, match="different settings"):
        opencode.providers_tree(ctx.config["models"] | {"tiers": tiers}, ctx)


WORKFLOW: dict[str, Any] = {
    "id": "w",
    "description": "Two  lines\nof description.",
    "parameters": {"go": "whether"},
    "loop": {"nodes": ["poll"], "max": 2, "until": "poll"},
    "nodes": [
        {"id": "start", "run": "true"},
        {"id": "poll", "depends": ["start"], "run": "true"},
        {"id": "judge", "depends": ["poll"], "actor": "auditor", "instruction": "Read {{rundir}}."},
        {"id": "ship", "depends": ["judge"], "run": "true", "when": {"go": ["yes"]}},
    ],
}


async def test_tekton_workflow_script_gates_every_node(ctx: RowContext) -> None:
    lines = claudecode.claude_workflow(None, ctx.per(WORKFLOW, "w")).splitlines()
    assert lines[0] == (
        'export const meta = {"name": "w", "description": "Two lines of description.", "phases": '
        '[{"title": "start"}, {"title": "poll"}, {"title": "judge"}, {"title": "ship"}]}'
    )
    assert 'const P = Object.assign({"go": ""}, args && typeof args === \'object\' ? args : {})' in lines
    assert '  for (let k = 1; k <= 2; k++) for (const id of ["poll"]) last = await run(`${id}_${k}`, id)' in lines
    assert 'const n_start = gate("start", [], () => true, null)' in lines
    assert (
        'const n_judge = gate("judge", [n_loop], () => true, () => think("judge", "auditor", "Read {{rundir}}.", ["poll"]))'
        in lines
    )
    assert 'const n_ship = gate("ship", [n_judge], () => ["yes"].includes(String(P["go"] ?? \'\')), null)' in lines
    assert lines[-1] == (
        "return {workflow: WORKFLOW, rundir: RUNDIR, steps: await Promise.all([n_start, n_judge, n_ship, n_loop])}"
    )


async def test_tekton_workflow_script_refuses_an_agent_in_a_loop(ctx: RowContext) -> None:
    looped = {**WORKFLOW, "loop": {"nodes": ["poll", "judge"], "max": 2, "until": "poll"}}
    with pytest.raises(RenderError, match=r"a loop with agent steps \(judge\)"):
        claudecode.claude_workflow(None, ctx.per(looped, "w"))


async def test_tekton_workflow_script_without_a_loop_has_none(ctx: RowContext) -> None:
    plain = {key: value for key, value in WORKFLOW.items() if key != "loop"}
    script = claudecode.claude_workflow(None, ctx.per(plain, "w"))
    assert ("n_loop" in script, 'const n_poll = gate("poll", [n_start], () => true, null)' in script) == (False, True)
