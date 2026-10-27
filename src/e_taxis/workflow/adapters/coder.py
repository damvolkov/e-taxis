"""adapters.coder: the coders under measurement — real CLIs, real prompts, pointed at a render, never the live tree.

A routing probe is only honest if it runs what the machine runs, with every competing description in the index: each
coder is driven through its own CLI in a clean session, its config home a sandbox whose corpus is the run's render.
OpenCode gets an XDG config home where `opencode/` is the render and every other entry links to the real one
(`OPENCODE_CONFIG_DIR` alone only layers over the global dir, so the live tree would load beneath); Claude Code gets
a throwaway `CLAUDE_CONFIG_DIR` whose entries link to the render, its credentials linked to the real ones (a refreshed
token must reach the real home) and its global config copied (a session writes it). Both sessions are marked
headless: no human command and no learning hook runs inside them.

What a session did is read from its event stream: the skills its skill tool loaded, the reference files any tool
named (`…/skills/<skill>/references/<file>.md`, from whichever argument a driver spells the path in), its text."""

import re
import shutil
from typing import TYPE_CHECKING, Any, Final

import anyio
import msgspec

from e_taxis.workflow.models.case import ProbeMode, ProbeResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
REFERENCE: Final[re.Pattern[str]] = re.compile(r"/skills/([^/]+)/references/([^/]+\.md)$")
HEADLESS: Final[Mapping[str, str]] = {"OPS_GLOBAL__HEADLESS": "1"}
### what the session is told to do, per mode: load and stop; load, read, open; never load.
HARNESS: Final[Mapping[ProbeMode, str]] = {
    ProbeMode.ACTIVATION: (
        "Load exactly the skills that genuinely apply to the task, one skill call per skill. "
        "Do not open any other file. Do not solve the task, write code, or chat. "
        "Then reply done and stop."
    ),
    ProbeMode.NAVIGATION: (
        "Load exactly the skills that genuinely apply to the task, then open only the "
        "reference files inside those skills you would actually need to answer it. "
        "Open nothing you would not use. Do not solve the task, write code, or chat. "
        "Then reply done and stop."
    ),
    ProbeMode.PRELOAD: (
        "Answer only from what is already in your context — the instruction files injected "
        "into your system prompt are part of it; recite the house wording, not general knowledge. "
        "Load no skill, open no file, call no tool. Only if the fact is truly absent from your "
        "context, say exactly: NO ESTA EN CONTEXTO. Then stop."
    ),
}
### the instrument's budget per mode: navigation loads, reads, then opens; a preload that holds answers in one turn.
TURNS: Final[Mapping[ProbeMode, int]] = {ProbeMode.ACTIVATION: 3, ProbeMode.NAVIGATION: 8, ProbeMode.PRELOAD: 2}
### OpenCode's agents per mode: the probe loads and stops; a preload answers, so it runs an agent that answers.
AGENTS: Final[Mapping[ProbeMode, str]] = {
    ProbeMode.ACTIVATION: "probe",
    ProbeMode.NAVIGATION: "probe",
    ProbeMode.PRELOAD: "plan",
}
### every billed field: cache creation and reads dominate a probe whose context is every skill description.
BILLED: Final[tuple[str, ...]] = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


##### UTILITIES #####
def references_coder(values: Iterable[Any]) -> frozenset[str]:
    """Reference files named by any of `values`, as `<skill>/<file>.md`: scanned, not keyed, since the drivers spell
    the path argument differently and a missed key would silently report nothing read."""
    found = (REFERENCE.search(value) for value in values if isinstance(value, str))
    return frozenset(f"{hit.group(1)}/{hit.group(2)}" for hit in found if hit)


async def link_coder(link: anyio.Path, source: Path | anyio.Path) -> None:
    """`link` → `source`, absolute: a relative target resolves from the link's own folder, never the caller's cwd."""
    await link.unlink(missing_ok=True)
    await link.symlink_to(await anyio.Path(source).absolute())


##### TYPES #####
class OpencodeCoder:
    """Satisfies CoderPort over `opencode run --format json`; `real` is the XDG config home the sandbox mirrors."""

    __slots__ = ("_command", "_real")

    def __init__(self, command: CommandPort, real: Path) -> None:
        self._command = command
        self._real = real

    ##### PRIVATE METHODS #####

    @staticmethod
    def _probe_part(part: Any) -> ProbeResult:
        """One event part as the little it says: a skill loaded and references named, a text, the tokens spent."""
        match part:
            case {"type": "tool", "tool": tool, "state": {"input": dict(payload)}}:
                ### OpenCode 1.x names the skill `name`; 2.x names it `id`.
                name = payload.get("name", payload.get("id"))
                loaded = frozenset({name}) if tool == "skill" and isinstance(name, str) else frozenset()
                return ProbeResult(loaded=loaded, opened=references_coder(payload.values()))
            case {"type": "text", "text": str(chunk)}:
                return ProbeResult(text=chunk)
            case {"type": "step-finish", "tokens": {"total": int(total)}}:
                return ProbeResult(tokens=total)
            case _:
                return ProbeResult()

    ############################################################

    ##### PUBLIC #####

    @classmethod
    def read(cls, raw: str) -> ProbeResult:
        """A `--format json` event stream → what the session loaded, opened, said and spent."""
        parts = [
            cls._probe_part(msgspec.json.decode(line).get("part", {}))
            for line in raw.splitlines()
            if line.startswith("{")
        ]
        return ProbeResult(
            loaded=frozenset().union(*(part.loaded for part in parts)),
            opened=frozenset().union(*(part.opened for part in parts)),
            text="\n".join(part.text for part in parts if part.text),
            tokens=sum(part.tokens for part in parts),
        )

    async def sandbox(self, flat: Path, root: Path) -> Mapping[str, str]:
        """Every real entry of the XDG config home linked, `opencode` → `flat`."""
        await anyio.Path(root).mkdir(parents=True, exist_ok=True)
        real = sorted([entry async for entry in anyio.Path(self._real).iterdir() if entry.name != "opencode"])
        _ = [await link_coder(anyio.Path(root / entry.name), entry) for entry in real]
        await link_coder(anyio.Path(root / "opencode"), flat)
        return {
            "XDG_CONFIG_HOME": str(root),
            "OPENCODE_CONFIG_DIR": str(flat),
            "OPENCODE_DISABLE_CLAUDE_CODE": "1",
            **HEADLESS,
        }

    async def probe(self, prompt: str, mode: ProbeMode, *, env: Mapping[str, str], limit: float) -> ProbeResult:
        raw = await self._command.run(
            "opencode",
            "run",
            "--agent",
            AGENTS[mode],
            "--format",
            "json",
            f"{HARNESS[mode]}\n\n{prompt}",
            limit=limit,
            env=env,
        )
        return self.read(raw)


class ClaudeCoder:
    """Satisfies CoderPort over `claude -p --output-format stream-json`; `real` is the Claude home whose credentials
    the sandbox borrows."""

    __slots__ = ("_command", "_real")

    def __init__(self, command: CommandPort, real: Path) -> None:
        self._command = command
        self._real = real

    ##### PRIVATE METHODS #####

    @staticmethod
    def _probe_block(block: Any) -> ProbeResult:
        match block:
            case {"type": "text", "text": str(chunk)}:
                return ProbeResult(text=chunk)
            case {"type": "tool_use", "name": tool, "input": dict(payload)}:
                skill = payload.get("skill")
                loaded = frozenset({skill}) if tool == "Skill" and isinstance(skill, str) else frozenset()
                return ProbeResult(loaded=loaded, opened=references_coder(payload.values()))
            case _:
                return ProbeResult()

    @classmethod
    def _probe_event(cls, event: Any) -> list[ProbeResult]:
        match event:
            case {"type": "assistant", "message": {"content": list(blocks)}}:
                return [cls._probe_block(block) for block in blocks]
            case {"type": "result", "usage": dict(usage)}:
                return [ProbeResult(tokens=sum(int(usage.get(field, 0)) for field in BILLED))]
            case _:
                return []

    ############################################################

    ##### PUBLIC #####

    @classmethod
    def read(cls, raw: str) -> ProbeResult:
        """A `stream-json` event stream → what the session loaded, opened, said and spent."""
        parts = [
            part
            for line in raw.splitlines()
            if line.startswith("{")
            for part in cls._probe_event(msgspec.json.decode(line))
        ]
        return ProbeResult(
            loaded=frozenset().union(*(part.loaded for part in parts)),
            opened=frozenset().union(*(part.opened for part in parts)),
            text="\n".join(part.text for part in parts if part.text),
            tokens=sum(part.tokens for part in parts),
        )

    async def sandbox(self, flat: Path, root: Path) -> Mapping[str, str]:
        """Credentials linked from the real home, its global config copied, every entry of `flat` as the corpus."""
        home = anyio.Path(root)
        await home.mkdir(parents=True, exist_ok=True)
        credentials, config = self._real / ".credentials.json", self._real.parent / ".claude.json"
        _ = await anyio.Path(credentials).exists() and await link_coder(home / ".credentials.json", credentials)
        _ = await anyio.Path(config).exists() and await anyio.to_thread.run_sync(
            shutil.copy2, config, root / ".claude.json"
        )
        _ = [await link_coder(home / entry.name, entry) async for entry in anyio.Path(flat).iterdir()]
        return {"CLAUDE_CONFIG_DIR": str(root), **HEADLESS}

    async def probe(self, prompt: str, mode: ProbeMode, *, env: Mapping[str, str], limit: float) -> ProbeResult:
        raw = await self._command.run(
            "claude",
            "-p",
            "--append-system-prompt",
            HARNESS[mode],
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-turns",
            str(TURNS[mode]),
            "--",
            prompt,
            limit=limit,
            env=env,
        )
        return self.read(raw)
