"""adapters.agent: one of the corpus's agents driven headless through OpenCode — and, when read-only, fenced.

`drive` runs the agent in an explicit directory (cwd and `PWD` agree), on a private server (`--standalone`: the
background service would read its own config and environment, not this run's), against the live tree, and only if
the tree declares the agent drivable: `opencode run --agent` on a subagent falls back to the default agent with
every permission, so a subagent is refused. Headless, an `ask` is fatal (`opencode run` auto-rejects it and disposes
the session), so every `ask` the agent meets — its own, and the global ones it inherits — is injected as `deny`
through `OPENCODE_CONFIG_CONTENT`. The session is marked `OPS_GLOBAL__HEADLESS` so no human-only command and no
learning hook runs inside it.

**Read-only is a fence, not a request.** OpenCode 2.0.28 honours the injected `edit: deny` (its private server
normalizes it into `permissions: [{action: edit, resource: "*", effect: deny}]`), but `edit` governs only the file
tools: the agents keep `shell: allow`, and one `sed -i`, `>` or `git apply` writes the repo anyway — which is how
a read-only session wrote into e-nous. Denying `shell` would blind the miners (git, the code-graph CLI). So a
read-only session runs under Landlock (`landrun`): it reads and executes everything, writes only OpenCode's own
state, cache and data and a private temp dir, and keeps the network. `--best-effort` could silently weaken the
fence, so the canary proves it holds before every read-only session; one that does not hold refuses the step."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.error import AgentError
from e_taxis.workflow.models.run import Reply

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.workflow.models.ports import CanaryPort, CommandPort

##### DEFAULTS #####
MODE: Final[re.Pattern[str]] = re.compile(r"^mode:\s*(\w+)\s*$", re.MULTILINE)
SUBAGENT: str = "subagent"
DEVICES: tuple[str, ...] = ("/dev/null", "/dev/tty")
CANARY: str = ".taxis-fence-canary"

type Rule = str | dict[str, str]


##### TYPES #####
class OpencodeAgent:
    """Satisfies AgentPort over the `opencode` CLI and, for read-only sessions, the `landrun` fence (its canary from
    the trial's own `LandrunFence`)."""

    __slots__ = ("_command", "_config", "_environ", "_fence", "_landrun", "_model", "_writable")

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
        self._command = command
        self._environ = environ
        self._fence = fence
        self._config = config
        self._landrun = landrun
        self._writable = tuple(writable)
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

    async def _drive_front(self, agent: str) -> str:
        flat = anyio.Path(self._config / "agents" / f"{agent}.md")
        match await flat.is_file():
            case False:
                msg = f"agent {agent!r} is not in {self._config}"
                raise AgentError(msg)
            case _:
                return (await flat.read_text()).split("\n---", 1)[0].removeprefix("---\n")

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

    def _drive_fenced(self, argv: Sequence[str], scratch: Path, names: Sequence[str]) -> tuple[str, ...]:
        """`argv` under Landlock: read and execute `/`, write only OpenCode's own dirs and `scratch`, any network,
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

    async def _drive_canary(self, scratch: Path, cwd: Path) -> None:
        match await self._fence.canary(scratch / "canary", cwd / CANARY):
            case True:
                return
            case _:
                msg = f"the read-only fence does not hold ({self._landrun}): refusing an unfenced read-only session"
                raise AgentError(msg)

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

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        """One headless session of a house agent in `cwd`; a subagent is refused, a read-only one fenced."""
        front = await self._drive_front(agent)
        match MODE.search(front):
            case re.Match() as found if found.group(1) == SUBAGENT:
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
        with TemporaryDirectory(prefix="e-taxis-agent-") as tmp:
            scratch = Path(tmp)
            env = {
                "PWD": str(cwd),
                "TMPDIR": tmp,
                "OPS_GLOBAL__HEADLESS": "1",
                "OPENCODE_CONFIG_CONTENT": msgspec.json.encode({"agent": {agent: override}}).decode(),
            }
            match readonly:
                case True:
                    await self._drive_canary(scratch, cwd)
                    argv = self._drive_fenced(argv, scratch, sorted(self._environ.keys() | env.keys()))
                case _:
                    pass
            raw = await self._command.run(*argv, limit=limit, cwd=cwd, env=env)
        return self.read(raw)
