"""tests/unit/e_taxis/workflow/adapters/harness: a whole workflow handed to a coder — what each is told, and granted."""

from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.adapters.harness import ClaudeHarness, Harness, HarnessTable, OpencodeHarness

if TYPE_CHECKING:
    from pathlib import Path

    from tests.unit.e_taxis.workflow.conftest import FakeCommand

    from e_taxis.workflow.adapters.agent import ClaudeAgent, OpencodeAgent

ARGS = {"value": "v", "rundir": "/abs/run", "nous": "/nous"}


async def test_harness_claude_runs_the_dynamic_workflow_granted_its_agents(
    fake_command: FakeCommand, claude_agent: ClaudeAgent, tmp_path: Path
) -> None:
    fake_command.answers[("env",)] = msgspec.json.encode({"result": "walked", "modelUsage": {}}).decode()
    said = await ClaudeHarness(fake_command, claude_agent, 60.0).run("w", ARGS, ("builder", "scout"), cwd=tmp_path)
    argv = list(fake_command.calls[0][0])
    grants = argv[argv.index("--allowedTools") + 1].split(",")
    assert said == "walked"
    assert argv[:3] == ["env", "-u", "CLAUDECODE"]
    assert argv[argv.index("--add-dir") + 1] == "/nous"
    assert argv[-1] == '/w {"value":"v","rundir":"/abs/run","nous":"/nous"}'
    assert grants[:2] == ["Workflow(w)", "Bash(taxis workflow step *)"]
    assert {"Write(//abs/run/**)", "Read", "Edit", "Bash", "mcp__graph", "mcp__inline"} <= set(grants)


async def test_harness_opencode_walks_workflow_with_asks_denied(
    fake_command: FakeCommand, opencode_agent: OpencodeAgent, tmp_path: Path
) -> None:
    fake_command.answers[("opencode",)] = '{"part": {"type": "text", "text": "walked"}}'
    table = HarnessTable({Harness.OPENCODE: OpencodeHarness(fake_command, opencode_agent, 60.0)})
    said = await table[Harness.OPENCODE].run("w", ARGS, ("builder",), cwd=tmp_path)
    argv, env = fake_command.calls[0]
    lead = msgspec.json.decode(env["OPENCODE_CONFIG_CONTENT"])["agent"]["orchestrator"]["permission"]
    assert said == "walked"
    assert argv[-1] == "/workflow w value=v rundir=/abs/run nous=/nous"
    assert lead["bash"]["*"] == "deny"
