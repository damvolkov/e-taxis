"""tests/unit/e_taxis/workflow/adapters/agent: driving OpenCode or Claude Code headless — every ask a deny, read-only
a fence, a subagent routed to Claude Code.

Defect 6 of the legacy driver: read-only was only `edit: deny` injected into OpenCode's config, and OpenCode 2 keeps
the agent's `shell: allow` — a read-only session wrote into the repo with a shell command. Read-only is now a
Landlock fence around the whole session: the unit tests assert the argv it builds and that an unproven fence refuses
the step; the slow test runs a stand-in `opencode` under the real landrun and watches its write into the checkout
fail."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.workflow.adapters.agent import ClaudeAgent, ModeAgent, OpencodeAgent
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.models.error import AgentError
from e_taxis.workflow.models.run import Reply

if TYPE_CHECKING:
    from pytest_resources import Resources

LANDRUN = Path("~/.local/bin/landrun").expanduser()
STREAM = '{"part": {"type": "text", "text": "done"}}\n'
USAGE = '{{"inputTokens": {i}, "outputTokens": {o}, "cacheReadInputTokens": {r}, "cacheCreationInputTokens": {w}}}'
RESULT = '{{"type": "result", "subtype": "success", "is_error": false, "result": "done", "modelUsage": {{{models}}}}}'


@pytest.mark.parametrize(
    ("own", "inherited", "injected"),
    [
        ("ask", None, "deny"),
        ("allow", {"*.env": "ask"}, None),
        ("deny", {"*.env": "ask"}, None),
        ({"*": "ask", "ls*": "allow"}, {"sudo *": "ask", "*": "allow"}, {"sudo *": "deny", "*": "deny"}),
        ({"ls*": "allow"}, None, None),
        (None, "ask", "deny"),
        (None, {"*": "allow", "rm -rf *": "ask"}, {"rm -rf *": "deny"}),
        (None, "allow", None),
    ],
)
async def test_agent_ask_becomes_deny_and_nothing_loosens(own: Any, inherited: Any, injected: Any) -> None:
    assert OpencodeAgent._rules_kind(own, inherited) == injected


async def test_agent_read_counts_cache_reads_apart() -> None:
    finish = '{{"part": {{"type": "step-finish", "tokens": {{"total": {t}, "input": 6, "output": {o}, "reasoning": 0, "cache": {{"write": {w}, "read": {r}}}}}}}}}'
    raw = "\n".join(
        [
            '{"part": {"type": "text", "text": "FINAL"}}',
            finish.format(t=20841, o=66, w=20769, r=0),
            finish.format(t=21143, o=129, w=239, r=20769),
            "not json",
        ]
    )
    assert OpencodeAgent.read(raw) == Reply(text="FINAL", tokens=6 + 66 + 20769 + 6 + 129 + 239, cached=20769)


async def test_agent_read_sums_opencode_2_tokens_without_a_total() -> None:
    raw = '{"part":{"type":"step-finish","tokens":{"input":6,"output":18,"reasoning":1,"cache":{"read":40}}}}'
    assert OpencodeAgent.read(raw) == Reply(text="", tokens=25, cached=40)


async def test_agent_drive_injects_every_ask_as_deny(
    opencode_agent: OpencodeAgent, fake_command, tmp_path: Path
) -> None:
    fake_command.answers[("opencode",)] = STREAM
    reply = await opencode_agent.drive("builder", "do it", cwd=tmp_path, limit=5.0, steps=3)
    argv, env = fake_command.calls[0]
    injected = msgspec.json.decode(env["OPENCODE_CONFIG_CONTENT"])["agent"]["builder"]
    assert argv == (
        "opencode",
        "run",
        "--standalone",
        "--agent",
        "builder",
        "--format",
        "json",
        "--model",
        "local/m",
        "do it",
    )
    assert injected == {
        "permission": {
            "bash": {"*": "deny"},
            "doom_loop": "deny",
            "shell": {"sudo *": "deny"},
        },
        "steps": 3,
    }
    assert (env["PWD"], env["OPS_GLOBAL__HEADLESS"]) == (str(tmp_path), "1")
    assert reply.text == "done"


async def test_agent_drive_readonly_runs_inside_the_fence(
    opencode_agent: OpencodeAgent, fake_command, tmp_path: Path
) -> None:
    await opencode_agent.drive("builder", "look", cwd=tmp_path, limit=5.0, readonly=True)
    argv, env = fake_command.calls[0]
    fence, _, inside = " ".join(argv).partition(" -- ")
    injected = msgspec.json.decode(env["OPENCODE_CONFIG_CONTENT"])["agent"]["builder"]["permission"]
    assert argv[:5] == ("/opt/landrun", "--best-effort", "--ignore-missing", "--rox", "/")
    assert f"--rw {tmp_path / 'cache'} --rw {env['TMPDIR']} --rw /dev/null" in fence
    assert "--unrestricted-network" in fence
    assert "--env OPENCODE_CONFIG_CONTENT" in fence
    assert "--env PATH" in fence
    assert "/usr/bin:/bin" not in fence
    assert inside.startswith("opencode run --standalone --agent builder")
    assert (injected["edit"], injected["write"]) == ("deny", "deny")


async def test_agent_drive_readonly_refuses_an_unproven_fence(
    opencode_agent: OpencodeAgent, fake_command, fence, tmp_path: Path
) -> None:
    fence.holds = False
    with pytest.raises(AgentError, match="read-only fence does not hold"):
        await opencode_agent.drive("builder", "look", cwd=tmp_path, limit=5.0, readonly=True)
    assert fake_command.calls == []


@pytest.mark.parametrize(
    ("agent", "why"), [("scout", "is a subagent"), ("ghost", "is not in")], ids=["subagent", "absent"]
)
async def test_agent_drive_refuses_what_it_cannot_drive(
    opencode_agent: OpencodeAgent, fake_command, tmp_path: Path, agent: str, why: str
) -> None:
    with pytest.raises(AgentError, match=why):
        await opencode_agent.drive(agent, "x", cwd=tmp_path, limit=5.0)
    assert fake_command.calls == []


async def test_agent_drive_without_a_global_config(
    opencode_agent: OpencodeAgent, opencode_tree: Path, fake_command, tmp_path: Path
) -> None:
    (opencode_tree / "opencode.jsonc").unlink()
    await opencode_agent.drive("builder", "x", cwd=tmp_path, limit=5.0)
    injected = msgspec.json.decode(fake_command.calls[0][1]["OPENCODE_CONFIG_CONTENT"])["agent"]["builder"]
    assert injected == {"permission": {"bash": {"*": "deny"}, "doom_loop": "deny"}}


@pytest.mark.slow
@pytest.mark.skipif(not LANDRUN.is_file(), reason="landrun is not installed")
@pytest.mark.parametrize(("readonly", "lands"), [(True, False), (False, True)], ids=["readonly", "writable"])
@pytest.mark.parametrize(
    ("kind", "agent"), [(OpencodeAgent, "builder"), (ClaudeAgent, "scout")], ids=["opencode", "claude"]
)
async def test_agent_readonly_session_cannot_write_the_checkout(
    resources: Resources,
    opencode_tree: Path,
    claude_tree: Path,
    tmp_path: Path,
    readonly: bool,
    lands: bool,
    kind: type[OpencodeAgent | ClaudeAgent],
    agent: str,
) -> None:
    """A stand-in CLI writes into its cwd with a plain shell redirect — what `edit: deny` never stopped."""
    bin_dir, checkout = tmp_path / "bin", tmp_path / "checkout"
    bin_dir.mkdir()
    checkout.mkdir()
    name = "claude" if kind is ClaudeAgent else "opencode"
    shutil.copy(resources.path / "workflow" / name, bin_dir / name)
    (bin_dir / name).chmod(0o755)
    environ = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    driver = kind(
        ShellCommand(environ),
        LandrunFence(LANDRUN),
        config=claude_tree if kind is ClaudeAgent else opencode_tree,
        landrun=LANDRUN,
        writable=(tmp_path / "cache",),
        environ=environ,
    )
    reply = await driver.drive(agent, "write", cwd=checkout, limit=30.0, readonly=readonly)
    assert reply.text == "done"
    assert (checkout / "written-by-agent").exists() is lands


async def test_agent_claude_read_sums_every_model() -> None:
    models = f'"opus": {USAGE.format(i=2, o=40, r=19424, w=12470)}, "haiku": {USAGE.format(i=1176, o=18, r=0, w=0)}'
    assert ClaudeAgent.read(RESULT.format(models=models)) == Reply(
        text="done", tokens=2 + 40 + 12470 + 1176 + 18, cached=19424
    )


async def test_agent_claude_read_refuses_an_error_result() -> None:
    raw = '{"type": "result", "subtype": "error_max_turns", "is_error": true, "result": null, "modelUsage": {}}'
    with pytest.raises(AgentError, match="error_max_turns"):
        ClaudeAgent.read(raw)


@pytest.mark.parametrize(
    ("agent", "readonly", "allowed", "denied"),
    [
        ("scout", False, "Read,Grep,Glob,Edit,Write,NotebookEdit,WebSearch,mcp__graph,mcp__inline", ()),
        (
            "scout",
            True,
            "Read,Grep,Glob,WebSearch,mcp__graph,mcp__inline",
            ("--disallowedTools", "Edit,Write,NotebookEdit"),
        ),
        ("builder", False, "Read,Edit,Bash", ()),
    ],
    ids=["writable", "readonly", "declared"],
)
async def test_agent_claude_drive_grants_what_the_definition_allows(
    claude_agent: ClaudeAgent,
    fake_command,
    tmp_path: Path,
    agent: str,
    readonly: bool,
    allowed: str,
    denied: tuple[str, ...],
) -> None:
    fake_command.answers[("/opt/landrun",)] = fake_command.answers[("claude",)] = RESULT.format(models="")
    reply = await claude_agent.drive(agent, "-do it", cwd=tmp_path, limit=5.0, readonly=readonly, steps=3)
    argv, env = fake_command.calls[0]
    assert argv[argv.index("claude") :] == (
        "claude",
        "-p",
        "--agent",
        agent,
        "--output-format",
        "json",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--max-turns",
        "3",
        "--allowedTools",
        allowed,
        *denied,
        "--",
        "-do it",
    )
    assert "--dangerously-skip-permissions" not in argv
    assert (env["PWD"], env["OPS_GLOBAL__HEADLESS"]) == (str(tmp_path), "1")
    assert reply == Reply(text="done")


async def test_agent_claude_drive_readonly_runs_inside_the_fence(
    claude_agent: ClaudeAgent, fake_command, tmp_path: Path
) -> None:
    fake_command.answers[("/opt/landrun",)] = RESULT.format(models="")
    await claude_agent.drive("scout", "look", cwd=tmp_path, limit=5.0, readonly=True)
    argv, env = fake_command.calls[0]
    fence, _, inside = " ".join(argv).partition(" -- ")
    assert argv[:5] == ("/opt/landrun", "--best-effort", "--ignore-missing", "--rox", "/")
    assert f"--rw {tmp_path / 'cache'} --rw {env['TMPDIR']} --rw /dev/null" in fence
    assert "--env PATH" in fence
    assert inside.startswith("claude -p --agent scout")
    assert "--max-turns" not in inside


async def test_agent_claude_drive_readonly_refuses_an_unproven_fence(
    claude_agent: ClaudeAgent, fake_command, fence, tmp_path: Path
) -> None:
    fence.holds = False
    with pytest.raises(AgentError, match="read-only fence does not hold"):
        await claude_agent.drive("scout", "look", cwd=tmp_path, limit=5.0, readonly=True)
    assert fake_command.calls == []


async def test_agent_claude_drive_refuses_an_absent_agent(
    claude_agent: ClaudeAgent, fake_command, tmp_path: Path
) -> None:
    with pytest.raises(AgentError, match="is not in"):
        await claude_agent.drive("ghost", "x", cwd=tmp_path, limit=5.0)
    assert fake_command.calls == []


@pytest.mark.parametrize(("agent", "driver"), [("scout", "claude"), ("builder", "opencode")], ids=["subagent", "all"])
async def test_agent_mode_routes_by_the_live_mode(
    mode_agent: ModeAgent, fake_command, tmp_path: Path, agent: str, driver: str
) -> None:
    fake_command.answers[("claude",)] = RESULT.format(models="")
    fake_command.answers[("opencode",)] = STREAM
    reply = await mode_agent.drive(agent, "x", cwd=tmp_path, limit=5.0)
    assert (fake_command.calls[0][0][0], reply.text) == (driver, "done")


async def test_agent_mode_reads_a_missing_mode_as_all(
    mode_agent: ModeAgent, opencode_tree: Path, fake_command, tmp_path: Path
) -> None:
    (opencode_tree / "agents" / "builder.md").write_text("---\npermission: {}\n---\nbody\n")
    fake_command.answers[("opencode",)] = STREAM
    await mode_agent.drive("builder", "x", cwd=tmp_path, limit=5.0)
    assert fake_command.calls[0][0][0] == "opencode"
