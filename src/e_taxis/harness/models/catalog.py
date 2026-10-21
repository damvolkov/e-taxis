"""models.catalog: the catalog entry — how one part of a harness's world is installed, probed, verified, undone.

The schema is design §3 and the YAML on disk is its only producer, so every model refuses unknown fields:
a typo in the catalog fails at load, never as a silently ignored recipe. `Catalog` is one load of the whole
directory — the entries that parsed, and every file that did not, with msgspec's reason."""

from datetime import date
from enum import StrEnum
from typing import Any

import msgspec
from msgspec import Struct, field

from e_taxis.harness.models.error import RecipeError


##### ENUMS #####
class Kind(StrEnum):
    """What the part is to the harness."""

    HARNESS = "harness"
    MCP = "mcp"
    PLUGIN = "plugin"
    HOOK = "hook"
    CLI = "cli"
    SERVICE = "service"
    ENV = "env"
    FILE = "file"
    MANAGED = "managed"


class Target(StrEnum):
    """Where an entry applies: one harness, or `system` — harness-independent, so every harness."""

    CLAUDECODE = "claudecode"
    OPENCODE = "opencode"
    OPENHUMAN = "openhuman"
    SYSTEM = "system"


class RecipeKey(StrEnum):
    """What a recipe is keyed by: a target, or `any` — the one recipe for every target the entry serves."""

    CLAUDECODE = "claudecode"
    OPENCODE = "opencode"
    OPENHUMAN = "openhuman"
    SYSTEM = "system"
    ANY = "any"


class Scope(StrEnum):
    """How far an install reaches."""

    MACHINE = "machine"
    USER = "user"
    PROJECT = "project"
    SERVICE = "service"
    ORG = "org"


class Primitive(StrEnum):
    """The installer a recipe runs through."""

    UV_TOOL = "uv-tool"
    NPM = "npm"
    BINARY = "binary"
    COMPOSE = "compose"
    CLAUDE_PLUGIN = "claude-plugin"
    CLAUDE_MCP = "claude-mcp"
    SETTINGS = "settings"
    FILE = "file"
    ENV = "env"


class Rollout(StrEnum):
    """How a profile takes a part: always, per project, or not at all."""

    FLOOR = "floor"
    PER_PROJECT = "per-project"
    OUT = "out"


##### DEFAULTS #####
### P2 writes the user and machine scopes; compose and the project scope arrive in P3 (design §6).
WRITABLE: frozenset[Scope] = frozenset({Scope.USER, Scope.MACHINE})
DEFERRED: frozenset[Primitive] = frozenset({Primitive.COMPOSE})


##### TYPES #####
class CatalogRecipe(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One primitive and its arguments — `with` in YAML, a keyword in Python."""

    primitive: Primitive
    with_: dict[str, Any] = field(default_factory=dict, name="with")

    def args[T](self, kind: type[T]) -> T:
        """`with`, typed as the primitive reads it; off-schema is a RecipeError naming the primitive."""
        try:
            return msgspec.convert(self.with_, kind)
        except msgspec.ValidationError as exc:
            msg = f"{self.primitive} recipe: {exc}"
            raise RecipeError(msg) from exc


class CatalogGate(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """What a human must settle before the part may be installed."""

    licence: str | None = None
    secrets: tuple[str, ...] = ()
    confirm: bool = False

    @property
    def needed(self) -> bool:
        return bool(self.licence or self.secrets or self.confirm)


class CatalogStatus(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """The rollout per profile, when it was last checked and on what evidence."""

    profile: dict[str, Rollout]
    checked: date
    evidence: str


class CatalogEntry(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One part id: what it is, where it applies, what comes first, how it is installed, probed and verified."""

    id: str
    kind: Kind
    targets: tuple[Target, ...]
    scope: Scope
    recipes: dict[RecipeKey, CatalogRecipe]
    probe: str
    verify: str
    status: CatalogStatus
    requires: tuple[str, ...] = ()
    uninstall: CatalogRecipe | None = None
    footprint: tuple[str, ...] = ()
    owns: tuple[str, ...] = ()
    gate: CatalogGate = field(default_factory=CatalogGate)
    flags: dict[str, Any] = field(default_factory=dict)

    def serves(self, target: Target) -> bool:
        return target in self.targets or Target.SYSTEM in self.targets

    def recipe(self, target: Target) -> CatalogRecipe | None:
        """The recipe keyed by the target itself, else the `any` one."""
        return self.recipes.get(RecipeKey(target)) or self.recipes.get(RecipeKey.ANY)

    def deferral(self, target: Target) -> str | None:
        """Why this phase does not write the entry for `target`, or None when it does."""
        match self.recipe(target):
            case CatalogRecipe(primitive=primitive) if primitive in DEFERRED:
                return f"deferred: {primitive} lands in P3"
            case _ if self.scope not in WRITABLE:
                return f"deferred: the {self.scope} scope lands in P3"
            case _:
                return None


class Catalog(Struct, frozen=True, kw_only=True):
    """One load: the entries that parsed, in file order, and `(file, reason)` for every one that did not."""

    entries: tuple[CatalogEntry, ...] = ()
    broken: tuple[tuple[str, str], ...] = ()
