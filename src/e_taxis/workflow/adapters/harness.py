"""adapters.harness: a whole workflow run by a coder harness, headless, in the directory taxis was invoked from.

`ClaudeHarness` sends `/<id> <args as JSON>` to `claude -p`: the transpiled dynamic workflow (`~/.claude/workflows/`),
`dontAsk`, granted the Workflow tool for that workflow alone, the two taxis plumbing commands, the run folder, and
every tool and MCP server the workflow's house agents declare in their live definitions. `OpencodeHarness` sends
`/workflow <id> k=v …` to `opencode run --standalone`, its lead's every `ask` injected as deny. Either way the parent
session's markers are dropped (`env -u`) so the child is a session of its own, and stdin is closed (the command
adapter's shape): an open stdin is what made `opencode run` hang. The harness's text is its say; the evidence is the
run folder, where every step left its ledger row."""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Final

import msgspec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from e_taxis.workflow.adapters.agent import ClaudeAgent, OpencodeAgent
    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
### the markers of the session that started taxis: a child claude must not believe it is nested in it.
PARENT: Final[tuple[str, ...]] = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_PID",
)
PLUMBING: Final[tuple[str, ...]] = ("Bash(taxis workflow step *)", "Bash(taxis workflow put *)", "Read", "Glob", "Grep")
LEAD: Final[str] = "orchestrator"


##### TYPES #####
class Harness(StrEnum):
    """The coder that walks the workflow."""

    CLAUDE = auto()
    OPENCODE = auto()


class ClaudeHarness:
    """Satisfies HarnessPort over `claude -p` and the transpiled dynamic workflow."""

    __slots__ = ("_agent", "_command", "_limit")

    def __init__(self, command: CommandPort, agent: ClaudeAgent, limit: float) -> None:
        self._command = command
        self._agent = agent
        self._limit = limit

    ##### PUBLIC #####

    async def run(self, workflow: str, args: Mapping[str, str], actors: tuple[str, ...], *, cwd: Path) -> str:
        """The workflow walked by Claude Code; the lead's last word."""
        granted = [tool for actor in actors for tool in await self._agent.allowed(actor)]
        ### the run folder is absolute; a Claude permission rule writes an absolute path with a leading `//`.
        reports = f"/{args['rundir']}/**"
        grants = dict.fromkeys((f"Workflow({workflow})", *PLUMBING, f"Write({reports})", f"Edit({reports})", *granted))
        argv = (
            "env",
            *(flag for name in PARENT for flag in ("-u", name)),
            "claude",
            "-p",
            "--output-format",
            "json",
            "--permission-mode",
            "dontAsk",
            "--allowedTools",
            ",".join(grants),
            "--add-dir",
            args.get("nous", str(cwd)),
            "--",
            f"/{workflow} {msgspec.json.encode(dict(args)).decode()}",
        )
        return self._agent.read(await self._command.run(*argv, limit=self._limit, cwd=cwd)).text


class OpencodeHarness:
    """Satisfies HarnessPort over `opencode run` and `/workflow`, walking the transpiled graph."""

    __slots__ = ("_agent", "_command", "_limit")

    def __init__(self, command: CommandPort, agent: OpencodeAgent, limit: float) -> None:
        self._command = command
        self._agent = agent
        self._limit = limit

    ##### PUBLIC #####

    async def run(self, workflow: str, args: Mapping[str, str], actors: tuple[str, ...], *, cwd: Path) -> str:
        """The workflow walked by OpenCode's lead; its last word. `actors` reach it through `/workflow`'s own tasks."""
        _ = actors
        rules = await self._agent.rules(LEAD)
        override = msgspec.json.encode({"agent": {LEAD: {"permission": rules}}}).decode()
        pairs = " ".join(f"{name}={value}" for name, value in args.items())
        argv = ("opencode", "run", "--standalone", "--format", "json", f"/workflow {workflow} {pairs}")
        said = await self._command.run(*argv, limit=self._limit, cwd=cwd, env={"OPENCODE_CONFIG_CONTENT": override})
        return self._agent.read(said).text


@dataclass(frozen=True, slots=True)
class HarnessTable:
    """The harnesses by name — built once at the composition root."""

    harnesses: Mapping[Harness, ClaudeHarness | OpencodeHarness]

    def __getitem__(self, harness: Harness) -> ClaudeHarness | OpencodeHarness:
        return self.harnesses[harness]
