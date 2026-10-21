"""adapters.harness.claudecode: a core projected for Claude Code — where every slot lands in `~/.claude`.

    persona slots          → CLAUDE.md, blocks in the order below
    skills/<id>            → skills/<id>/SKILL.md (frontmatter, `# id`, instructions) + references as they are
    agents/<id>            → agents/<id>.md (frontmatter, prompt); denied house tools → `disallowedTools`
    commands/<id>          → commands/<id>.md (frontmatter, template); `${name}` → `$name`
    config/main            → settings.json `$schema` `model` `effortLevel` `tui`; rules/instructions.md `@` imports
    config/permissions     → settings.json `permissions`
    config/hooks           → settings.json `hooks`; config/hooks/* → hooks/*
    config/mcp             → user-scope registrations (`claude mcp add-json`); config/mcp/* → mcp/*

Pure: a core and the tree it lands in, in; a render out. `{out}` in the core binds to that tree. Frontmatter is
YAML as e-serde writes it, so a render is byte for byte what the e-nous transpiler wrote before it."""

import re
import shlex
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import eserde

from e_taxis.harness.models.brain import BrainFile, BrainKey, BrainRender, BrainServer
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import CoreError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from e_taxis.harness.models.core import Core, CoreAgent, CoreCommand, CoreHook, CoreServer, CoreSkill

##### DEFAULTS #####
SCHEMA: str = "https://json.schemastore.org/claude-code-settings.json"
SETTINGS: str = "settings.json"
GOVERNED: tuple[str, ...] = ("skills", "agents", "commands")
### a `${name}` (or `$name`) in a command template: the named argument it refers to.
NAME: Final = re.compile(r"\$\{?([a-z_][a-z0-9_-]*)\}?(?!\w)")

### the persona document: (form, heading, slots, join). `h1`, `para`, `quote` form the preamble.
BLOCKS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("h1", "", ("name",), "\n\n"),
    ("para", "", ("essence",), "\n\n"),
    ("quote", "", ("epigraph",), "\n\n"),
    ("h2", "Damien", ("origin",), "\n\n"),
    ("h2", "One mind, two materials", ("unity",), "\n\n"),
    ("h2", "Temperament", ("temperament",), "\n\n"),
    ("h2", "The engineer", ("face",), "\n\n"),
    ("h2", "Philosophy and logic", ("stance", "reasoning"), "\n"),
    ("h2", "Voice", ("voice", "critique"), "\n"),
    ("h2", "Method: prudence before action", ("prudence", "method"), "\n"),
    ("h2", "Honesty", ("honesty",), "\n\n"),
    ("h2", "Engineering soul", ("soul",), "\n\n"),
    ("h2", "Knowledge architecture", ("knowledge",), "\n\n"),
    ("h2", "Software categories", ("categories",), "\n\n"),
    ("h2", "Skill creation rules", ("rules",), "\n\n"),
    ("h2", "Operating contract", ("conduct", "contract"), "\n"),
    ("h2", "Skills", ("skills",), "\n\n"),
)
PREFIX: Final[Mapping[str, str]] = MappingProxyType({"h1": "# ", "para": "", "quote": "> ", "h2": "## {heading}\n\n"})

### a house permission key denied outright → the Claude Code tools it vetoes, in this order.
DENIED: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "read": ("Read",),
        "glob": ("Glob",),
        "grep": ("Grep",),
        "bash": ("Bash",),
        "edit": ("Edit", "Write", "NotebookEdit"),
        "task": ("Agent",),
        "todowrite": ("TodoWrite", "TaskCreate", "TaskGet", "TaskList", "TaskUpdate"),
        "webfetch": ("WebFetch",),
        "websearch": ("WebSearch",),
        "lsp": ("LSP",),
        "question": ("AskUserQuestion",),
        "skill": ("Skill",),
    }
)


##### TYPES #####
class ClaudecodeHarness:
    """Satisfies HarnessPort for Claude Code."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_markdown(front: Mapping[str, Any], body: str, title: str = "") -> bytes:
        """Frontmatter of the non-empty fields, an optional `# title`, the body; one trailing newline."""
        kept = {key: value for key, value in front.items() if value not in (None, "", [], (), {})}
        yaml = eserde.dumps(kept, format=eserde.Format.YAML).decode().rstrip()
        heading = f"# {title}\n\n" if title else ""
        return f"---\n{yaml}\n---\n\n{heading}{body.rstrip()}\n".encode()

    @staticmethod
    def _common_out(value: str, tree: Path) -> str:
        return value.replace("{out}", str(tree))

    @classmethod
    def _render_skill(cls, ident: str, skill: CoreSkill, refs: Mapping[str, bytes]) -> tuple[BrainFile, ...]:
        front = {
            "name": skill.name,
            "description": skill.description,
            "license": skill.license,
            "compatibility": skill.compatibility,
            "metadata": skill.metadata,
        }
        entry = BrainFile(path=f"skills/{ident}/SKILL.md", data=cls._common_markdown(front, skill.instructions, ident))
        return (entry, *(BrainFile(path=f"skills/{ident}/{ref}", data=data) for ref, data in refs.items()))

    @classmethod
    def _render_agent(cls, ident: str, agent: CoreAgent) -> BrainFile:
        denied = [
            tool
            for key, tools in DENIED.items()
            if (rule := agent.permission.get(key)) == "deny"
            or (isinstance(rule, dict) and set(rule.values()) == {"deny"})
            for tool in tools
        ]
        front = {
            "name": agent.id,
            "description": agent.description,
            "skills": list(agent.skills_preload),
            "maxTurns": agent.max_steps,
            "disallowedTools": denied,
        }
        return BrainFile(path=f"agents/{ident}.md", data=cls._common_markdown(front, agent.prompt))

    @classmethod
    def _render_command(cls, ident: str, command: CoreCommand) -> BrainFile:
        names = list(command.inputs)
        ### Claude counts arguments from 0: a positional $1 would land shifted, so named arguments are emitted.
        body = NAME.sub(lambda m: f"${m.group(1)}" if m.group(1) in names else m.group(0), command.template)
        front = {
            "description": command.description,
            "arguments": names,
            "argument-hint": " ".join(f"[{name}]" for name in names),
        }
        return BrainFile(path=f"commands/{ident}.md", data=cls._common_markdown(front, body))

    @staticmethod
    def _render_block(form: str, heading: str, slots: tuple[str, ...], join: str, persona: Mapping[str, str]) -> str:
        match [slot for slot in slots if slot not in persona]:
            case []:
                present = [text for slot in slots if (text := persona[slot].strip("\n"))]
                return PREFIX[form].format(heading=heading) + join.join(present) if present else ""
            case missing:
                msg = f"CLAUDE.md: persona slot(s) {', '.join(missing)} declared by no layer of the core"
                raise CoreError(msg)

    @classmethod
    def _render_persona(cls, persona: Mapping[str, str]) -> BrainFile:
        built = [text for block in BLOCKS if (text := cls._render_block(*block, persona))]
        headings = tuple(heading for form, heading, _, _ in BLOCKS if form == "h2")
        return BrainFile(path="CLAUDE.md", data="\n\n".join(built).encode(), headings=headings)

    @classmethod
    def _render_hooks(cls, hooks: Mapping[str, tuple[CoreHook, ...]], tree: Path) -> dict[str, list[dict[str, Any]]]:
        return {
            event: [
                ({"matcher": matcher} if matcher else {})
                | {
                    "hooks": [
                        {"type": "command", "command": shlex.join(cls._common_out(arg, tree) for arg in hook.run)}
                    ]
                }
                for hook in entries
                for matcher in hook.matchers or ("",)
            ]
            for event, entries in hooks.items()
        }

    @classmethod
    def _render_keys(cls, core: Core, tree: Path) -> tuple[BrainKey, ...]:
        try:
            model = core.main.model.alias[Target.CLAUDECODE]
        except KeyError:
            msg = "config/main.yaml: model.alias names no `claudecode` session model"
            raise CoreError(msg) from None
        owned = {
            "$schema": SCHEMA,
            "model": model,
            "effortLevel": core.main.effort,
            "tui": core.main.display.get("tui"),
            "permissions": {
                "allow": list(core.permissions.rules.allow),
                "defaultMode": core.permissions.default_mode,
                "additionalDirectories": list(core.permissions.external_dirs),
            },
            "hooks": cls._render_hooks(core.hooks, tree),
        }
        return tuple(BrainKey(file=SETTINGS, key=key, value=value) for key, value in owned.items())

    @classmethod
    def _render_server(cls, name: str, server: CoreServer, tree: Path) -> BrainServer:
        """In the shape Claude stores it: stdio always carries `args`; env and headers only when set."""
        bind: Callable[[str], str] = partial(cls._common_out, tree=tree)
        shape = (
            {
                "type": "stdio",
                "command": bind(server.command[0]),
                "args": [bind(arg) for arg in server.command[1:]],
                "env": {key: bind(value) for key, value in server.env.items()},
            }
            if server.command
            else {"type": "http", "url": bind(server.url), "headers": dict(server.headers)}
        )
        return BrainServer(name=name, config={key: value for key, value in shape.items() if value or key == "args"})

    ############################################################

    ##### PUBLIC #####

    def render(self, core: Core, tree: Path) -> BrainRender:
        instructions = "".join(f"@{self._common_out(path, tree)}\n" for path in core.main.instructions)
        files = (
            *(
                file
                for ident, skill in core.skills.items()
                for file in self._render_skill(ident, skill, core.references.get(ident, {}))
            ),
            *(self._render_agent(ident, agent) for ident, agent in core.agents.items()),
            *(self._render_command(ident, command) for ident, command in core.commands.items()),
            self._render_persona(core.persona),
            BrainFile(path="rules/instructions.md", data=instructions.encode()),
            *(BrainFile(path=path, data=data) for path, data in core.carried.items()),
        )
        servers = tuple(
            self._render_server(name, server, tree)
            for name, server in core.mcp.servers.items()
            if server.enabled and Target.CLAUDECODE in server.backends
        )
        return BrainRender(
            target=Target.CLAUDECODE,
            files=files,
            keys=self._render_keys(core, tree),
            servers=servers,
            governed=GOVERNED,
        )
