"""adapters.agent: one of the corpus's agents driven headless — through OpenCode, or through Claude Code when the live
OpenCode tree marks it a subagent — and, when read-only, fenced.

`OpencodeAgent.drive` runs the agent in an explicit directory (cwd and `PWD` agree), on a private server
(`--standalone`: the background service would read its own config and environment, not this run's), against the live
tree, and only if the tree declares the agent drivable: `opencode run --agent` on a subagent falls back to the
default agent with every permission, so a subagent is refused. Headless, an `ask` is fatal (`opencode run`
auto-rejects it and disposes the session), so every `ask` the agent meets — its own, and the global ones it inherits —
is injected as `deny` through `OPENCODE_CONFIG_CONTENT`. The session is marked `OPS_GLOBAL__HEADLESS` so no
human-only command and no learning hook runs inside it.

`ClaudeAgent.drive` runs the same agent from the live Claude Code tree (`claude -p --agent`), which runs a subagent
headless natively and applies the definition's own `disallowedTools`. It never skips permissions: the session is
`dontAsk` (what would prompt is denied, as OpenCode's asks are), granted the definition's `tools` — or, when it names
none, every approvable built-in it does not disallow — plus its `mcpServers`; read-only drops and denies the file
writers. `ModeAgent` routes each agent by its live OpenCode mode, a frozen table mode → driver.

**Read-only is a fence, not a request.** OpenCode 2.0.28 honours the injected `edit: deny` (its private server
normalizes it into `permissions: [{action: edit, resource: "*", effect: deny}]`), but `edit` governs only the file
tools: the agents keep `shell: allow`, and one `sed -i`, `>` or `git apply` writes the repo anyway — which is how
a read-only session wrote into e-nous. Denying `shell` would blind the miners (git, the code-graph CLI). So a
read-only session — either driver — runs under Landlock (`landrun`): it reads and executes everything, writes only
the drivers' own state, cache and data and a private temp dir, and keeps the network. `--best-effort` could silently
weaken the fence, so the canary proves it holds before every read-only session; one that does not hold refuses the
step."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.error import AgentError
from e_taxis.workflow.models.run import Reply
from e_taxis.workflow.models.workflow import AgentMode

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.workflow.models.ports import AgentPort, CanaryPort, CommandPort

##### DEFAULTS #####
MODE: Final[re.Pattern[str]] = re.compile(r"^mode:\s*(\w+)\s*$", re.MULTILINE)
DEVICES: tuple[str, ...] = ("/dev/null", "/dev/tty")
CANARY: str = ".taxis-fence-canary"
### Claude Code's built-ins a definition may be granted; Read/Grep/Glob need no approval but are named for the record.
GRANTS: Final[tuple[str, ...]] = (
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
)
WRITERS: Final[tuple[str, ...]] = ("Edit", "Write", "NotebookEdit")
FRESH: Final[tuple[str, ...]] = ("inputTokens", "outputTokens", "cacheCreationInputTokens")

type Rule = str | dict[str, str]


##### TYPES #####
class LandrunAgent:
    """A headless driver over a live agent tree (`config`): the definition read, a session run in `cwd` and, read-only,
    under the `landrun` fence (its canary from the trial's own `LandrunFence`)."""

    __slots__ = ("_command", "_config", "_environ", "_fence", "_landrun", "_writable")

    def __init__(
        self,
        command: CommandPort,
        fence: CanaryPort,
        *,
        config: Path,
        landrun: Path,
        writable: Sequence[Path],
        environ: Mapping[str, str],
    ) -> None:
        self._command = command
        self._environ = environ
        self._fence = fence
        self._config = config
        self._landrun = landrun
        self._writable = tuple(writable)

    ##### PRIVATE METHODS #####

    async def _common_front(self, agent: str) -> str:
        """The agent's definition front matter, as text."""
        flat = anyio.Path(self._config / "agents" / f"{agent}.md")
        match await flat.is_file():
            case False:
                msg = f"agent {agent!r} is not in {self._config}"
                raise AgentError(msg)
            case _:
                return (await flat.read_text()).split("\n---", 1)[0].removeprefix("---\n")

    def _common_fenced(self, argv: Sequence[str], scratch: Path, names: Sequence[str]) -> tuple[str, ...]:
        """`argv` under Landlock: read and execute `/`, write only the driver's own dirs and `scratch`, any network,
        the environment passed by name (no value lands in the argv)."""
        writable = (*map(str, (*self._writable, scratch)), *DEVICES)
        return (
            str(self._landrun),
            "--best-effort",
            "--ignore-missing",
            "--rox",
            "/",
            *(flag for path in writable for flag in ("--rw", path)),
            "--unrestricted-network",
            *(flag for name in names for flag in ("--env", name)),
            "--",
            *argv,
        )

    async def _common_canary(self, scratch: Path, cwd: Path) -> None:
        match await self._fence.canary(scratch / "canary", cwd / CANARY):
            case True:
                return
            case _:
                msg = f"the read-only fence does not hold ({self._landrun}): refusing an unfenced read-only session"
                raise AgentError(msg)

    async def _common_session(
        self, argv: Sequence[str], *, cwd: Path, limit: float, readonly: bool, env: Mapping[str, str]
    ) -> str:
        """One session's stdout: `argv` run in `cwd` with a private temp dir, marked headless; read-only, fenced."""
        with TemporaryDirectory(prefix="e-taxis-agent-") as tmp:
            scratch = Path(tmp)
            env = {"PWD": str(cwd), "TMPDIR": tmp, "OPS_GLOBAL__HEADLESS": "1", **env}
            match readonly:
                case True:
                    await self._common_canary(scratch, cwd)
                    argv = self._common_fenced(argv, scratch, sorted(self._environ.keys() | env.keys()))
                case _:
                    pass
            return await self._command.run(*argv, limit=limit, cwd=cwd, env=env)


class OpencodeAgent(LandrunAgent):
    """Satisfies AgentPort over the `opencode` CLI and, for read-only sessions, the `landrun` fence."""

    __slots__ = ("_model",)

    def __init__(
        self,
        command: CommandPort,
        fence: CanaryPort,
        *,
        config: Path,
        landrun: Path,
        writable: Sequence[Path],
        environ: Mapping[str, str],
        model: str = "",
    ) -> None:
        super().__init__(command, fence, config=config, landrun=landrun, writable=writable, environ=environ)
        self._model = model

    ##### PRIVATE METHODS #####

    @staticmethod
    def _rules_denied(rule: Any) -> dict[str, str]:
        """The `ask` patterns of a rule map, as `deny`."""
        match rule:
            case dict():
                return {pattern: "deny" for pattern, action in rule.items() if action == "ask"}
            case _:
                return {}

    @classmethod
    def _rules_kind(cls, own: Any, inherited: Any) -> Rule | None:
        """What one permission kind injects headless, given the agent's rule and the global one it sits on.

        The agent's string wins over every global pattern, so it is replaced only when it is `ask` — never by a map,
        which would loosen a `deny`. A map gains its own and the inherited asks as denies."""
        match own:
            case str():
                return "deny" if own == "ask" else None
            case dict():
                return (cls._rules_denied(inherited) | cls._rules_denied(own)) or None
            case _:
                return "deny" if inherited == "ask" else cls._rules_denied(inherited) or None

    @staticmethod
    def _rules_inherited(main: Any) -> dict[str, Any]:
        """The global permissions as kind → rule: OpenCode 1's `permission` map, or OpenCode 2's `permissions` list."""
        listed = main.get("permissions") or []
        flat = {rule["action"]: {} for rule in listed}
        _ = [flat[rule["action"]].update({rule["resource"]: rule["effect"]}) for rule in listed]
        return (main.get("permission") or {}) | flat

    @staticmethod
    def _common_mode(front: str) -> AgentMode:
        return AgentMode(found.group(1)) if (found := MODE.search(front)) else AgentMode.ALL

    async def _drive_rules(self, front: str) -> dict[str, Rule]:
        """The permissions to inject so a headless session meets no `ask`: every ask becomes deny."""
        own = (eserde.loads(front, format=eserde.Format.YAML) or {}).get("permission") or {}
        main = anyio.Path(self._config / "opencode.jsonc")
        loaded = eserde.loads(await main.read_text(), format=eserde.Format.JSONC) if await main.is_file() else {}
        inherited = self._rules_inherited(loaded or {})
        rules = {
            kind: rule
            for kind in sorted(own.keys() | inherited.keys())
            if (rule := self._rules_kind(own.get(kind), inherited.get(kind))) is not None
        }
        return rules | ({} if "doom_loop" in own or "doom_loop" in inherited else {"doom_loop": "deny"})

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def read(raw: str) -> Reply:
        """A `--format json` event stream → its text parts joined; fresh tokens and cache reads summed apart."""
        parts = [msgspec.json.decode(line).get("part", {}) for line in raw.splitlines() if line.startswith("{")]
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        steps = [part.get("tokens", {}) for part in parts if part.get("type") == "step-finish"]
        cached = sum(step.get("cache", {}).get("read", 0) for step in steps)
        spent = sum(
            step.get("total") or sum(step.get(key, 0) for key in ("input", "output", "reasoning")) for step in steps
        )
        return Reply(
            text=text, tokens=spent - cached if any("total" in step for step in steps) else spent, cached=cached
        )

    async def rules(self, agent: str) -> dict[str, Rule]:
        """The permissions that keep a headless session of `agent` from meeting an `ask`: every ask denied."""
        return await self._drive_rules(await self._common_front(agent))

    async def mode(self, agent: str) -> AgentMode:
        """The agent's mode in the live tree; an agent the tree lacks raises."""
        return self._common_mode(await self._common_front(agent))

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        """One headless session of a house agent in `cwd`; a subagent is refused, a read-only one fenced."""
        front = await self._common_front(agent)
        match self._common_mode(front):
            case AgentMode.SUBAGENT:
                msg = f"agent {agent!r} is a subagent: `opencode run` would fall back to the default agent"
                raise AgentError(msg)
            case _:
                pass
        locked = {"edit": "deny", "write": "deny"} if readonly else {}
        override = {"permission": await self._drive_rules(front) | locked} | ({"steps": steps} if steps else {})
        argv = (
            "opencode",
            "run",
            "--standalone",
            "--agent",
            agent,
            "--format",
            "json",
            *(("--model", self._model) if self._model else ()),
            prompt,
        )
        env = {"OPENCODE_CONFIG_CONTENT": msgspec.json.encode({"agent": {agent: override}}).decode()}
        return self.read(await self._common_session(argv, cwd=cwd, limit=limit, readonly=readonly, env=env))


class ClaudeAgent(LandrunAgent):
    """Satisfies AgentPort over the `claude` CLI (Claude Code 2.1.31x) and, for read-only sessions, the `landrun`
    fence. The model is the definition's own: OpenCode's `TAXIS_WORKFLOW_MODEL` names no Claude model."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _drive_names(value: Any) -> tuple[str, ...]:
        """A definition's tool list: Claude's comma string, or a YAML list."""
        match value:
            case str():
                return tuple(name for part in value.split(",") if (name := part.strip()))
            case list():
                return tuple(map(str, value))
            case _:
                return ()

    @staticmethod
    def _drive_servers(value: Any) -> tuple[str, ...]:
        """The MCP servers a definition reaches: a name, or an inline `{name: config}`."""
        return tuple(name for item in value or () for name in ((item,) if isinstance(item, str) else item))

    @classmethod
    def _drive_grants(cls, front: str, *, readonly: bool) -> tuple[str, ...]:
        """`--allowedTools` and, read-only, `--disallowedTools`: what the definition allows, never a file writer when
        read-only."""
        definition = eserde.loads(front, format=eserde.Format.YAML) or {}
        denied = {*cls._drive_names(definition.get("disallowedTools")), *(WRITERS if readonly else ())}
        allowed = [
            *(tool for tool in cls._drive_names(definition.get("tools")) or GRANTS if tool not in denied),
            *(f"mcp__{server}" for server in cls._drive_servers(definition.get("mcpServers"))),
        ]
        return (
            *(("--allowedTools", ",".join(allowed)) if allowed else ()),
            *(("--disallowedTools", ",".join(WRITERS)) if readonly else ()),
        )

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def read(raw: str) -> Reply:
        """A `--output-format json` result → its text; fresh tokens (input, output, cache writes) and cache reads
        summed apart over every model the session used. An error result raises."""
        result = msgspec.json.decode(raw)
        match result:
            case {"is_error": True}:
                msg = f"the Claude Code session ended in {result.get('subtype')}: {result.get('errors') or ''}"
                raise AgentError(msg)
            case _:
                usage = list((result.get("modelUsage") or {}).values())
                return Reply(
                    text=result.get("result") or "",
                    tokens=sum(model.get(key, 0) for model in usage for key in FRESH),
                    cached=sum(model.get("cacheReadInputTokens", 0) for model in usage),
                )

    async def allowed(self, agent: str) -> tuple[str, ...]:
        """What a live definition grants, as `--allowedTools` names: its tools (every approvable one when it names
        none, less what it disallows) and its MCP servers."""
        definition = eserde.loads(await self._common_front(agent), format=eserde.Format.YAML) or {}
        denied = set(self._drive_names(definition.get("disallowedTools")))
        return (
            *(tool for tool in self._drive_names(definition.get("tools")) or GRANTS if tool not in denied),
            *(f"mcp__{server}" for server in self._drive_servers(definition.get("mcpServers"))),
        )

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        """One headless session of a house agent in `cwd`, a subagent included; a read-only one fenced."""
        front = await self._common_front(agent)
        ### `--` ends the options: the variadic tool lists cannot swallow the prompt, nor a leading `-` become a flag.
        argv = (
            "claude",
            "-p",
            "--agent",
            agent,
            "--output-format",
            "json",
            "--permission-mode",
            "dontAsk",
            "--no-session-persistence",
            *(("--max-turns", str(steps)) if steps else ()),
            *self._drive_grants(front, readonly=readonly),
            "--",
            prompt,
        )
        return self.read(await self._common_session(argv, cwd=cwd, limit=limit, readonly=readonly, env={}))


class ModeAgent:
    """Satisfies AgentPort: each agent goes to the driver its live OpenCode mode names — a subagent to Claude Code,
    which runs it headless natively; a primary or `all` agent to OpenCode."""

    __slots__ = ("_drivers", "_opencode")

    def __init__(self, opencode: OpencodeAgent, claude: AgentPort) -> None:
        self._opencode = opencode
        self._drivers: Mapping[AgentMode, AgentPort] = MappingProxyType(
            {AgentMode.SUBAGENT: claude, AgentMode.PRIMARY: opencode, AgentMode.ALL: opencode}
        )

    ##### PUBLIC #####

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        """One headless session, by whichever driver can run this agent; an agent the OpenCode tree lacks raises."""
        driver = self._drivers[await self._opencode.mode(agent)]
        return await driver.drive(agent, prompt, cwd=cwd, limit=limit, readonly=readonly, steps=steps)
