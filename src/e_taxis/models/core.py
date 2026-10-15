"""models.core: the content contract — what an e-engineer core holds, entity by entity, and where each one lives.

e-engineer owns the content; e-taxis owns this shape and every projection of it. A field is a slot the core
may fill; a harness adapter decides where, and whether, each slot lands. Unknown fields are ignored on
purpose: house-only slots (`mode`, `hidden`, `skills_ondemand`…) ride in the same manifests and no
projection reads them. A body slot is `{source: file}` beside its manifest; the reader embeds it and lifts the
envelope, so a model only ever holds text."""

from enum import StrEnum
from typing import Any

from msgspec import Struct

##### DEFAULTS #####
BASE: str = "core/base"
FACET: str = "core/engineer"
PERSONA: str = "persona.yaml"
CONFIG: str = "config"
### config side files travel to the same relative path in the tree: hooks/<script>, mcp/<file>.
CARRIED: tuple[str, ...] = ("hooks", "mcp")


##### ENUMS #####
class CoreEntity(StrEnum):
    """An instanced entity: one directory per id under the facet, one manifest in it."""

    SKILL = "skill"
    AGENT = "agent"
    COMMAND = "command"

    @property
    def folder(self) -> str:
        return f"{self.value}s"

    @property
    def manifest(self) -> str:
        return f"{self.value}.yaml"


##### INSTANCES #####
class CoreSkill(Struct, frozen=True, kw_only=True):
    name: str
    description: str
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, Any] = {}
    instructions: str = ""
    references: tuple[str, ...] = ()


class CoreAgent(Struct, frozen=True, kw_only=True):
    """`permission` is the house map (tool → allow/deny/ask, or pattern → rule); a projection reads what it can."""

    id: str
    description: str
    permission: dict[str, Any] = {}
    skills_preload: tuple[str, ...] = ()
    max_steps: int | None = None
    prompt: str = ""


class CoreCommand(Struct, frozen=True, kw_only=True):
    """`inputs` declares the named arguments, in order; `${name}` in the template refers to one."""

    id: str
    description: str
    inputs: dict[str, Any] = {}
    template: str = ""


class CorePersona(Struct, frozen=True):
    """One layer's slot registry: slot → text."""

    slots: dict[str, str]


##### CONFIG #####
class CoreServer(Struct, frozen=True, kw_only=True):
    """An MCP server: a local argv (stdio) or a remote url, exactly one. `{out}` is the tree it lands in."""

    command: tuple[str, ...] = ()
    url: str = ""
    env: dict[str, str] = {}
    headers: dict[str, str] = {}
    enabled: bool = True
    backends: tuple[str, ...] = ("opencode", "claudecode")

    def __post_init__(self) -> None:
        match (bool(self.command), bool(self.url)):
            case (True, False) | (False, True):
                pass
            case _:
                msg = "an MCP server is a `command` or a `url`, exactly one"
                raise ValueError(msg)


class CoreMcp(Struct, frozen=True):
    servers: dict[str, CoreServer] = {}


class CoreModel(Struct, frozen=True):
    """Tiers are opencode's; a harness that sees no tiers takes its alias."""

    alias: dict[str, str] = {}


class CoreMain(Struct, frozen=True, kw_only=True):
    """`instructions` are paths loaded into every session; `{out}` is the tree they land in."""

    model: CoreModel = CoreModel()
    instructions: tuple[str, ...] = ()
    effort: str = ""
    display: dict[str, Any] = {}


class CoreRules(Struct, frozen=True):
    allow: tuple[str, ...] = ()


class CorePermissions(Struct, frozen=True, kw_only=True):
    default_mode: str = ""
    external_dirs: tuple[str, ...] = ()
    rules: CoreRules = CoreRules()


class CoreHook(Struct, frozen=True, kw_only=True):
    """One command per matcher; an event that takes no matcher lists none."""

    run: tuple[str, ...]
    matchers: tuple[str, ...] = ()


##### AGGREGATE #####
class Core(Struct, frozen=True, kw_only=True):
    """One read of a core: the persona slots of `core/base` and the facet (a slot lives in one layer), every
    instance by id, the config modules, and the side files carried as they are (`hooks/x`, `mcp/x`)."""

    persona: dict[str, str]
    skills: dict[str, CoreSkill]
    agents: dict[str, CoreAgent]
    commands: dict[str, CoreCommand]
    main: CoreMain
    permissions: CorePermissions
    hooks: dict[str, tuple[CoreHook, ...]]
    mcp: CoreMcp
    carried: dict[str, bytes]
    references: dict[str, dict[str, bytes]]
