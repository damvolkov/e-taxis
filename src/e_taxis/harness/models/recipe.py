"""models.recipe: the `with` of each primitive, typed — what an adapter reads out of a catalog recipe.

Unknown keys are ignored on purpose: catalog recipes carry notes for humans (`note`, `bin`, `ephemeral`).
The uninstall side needs less than the install side, so each install shape extends its uninstall shape."""

from typing import Any, Literal

from msgspec import Struct, field


##### BINARY #####
class RecipeBinaryPath(Struct, frozen=True, kw_only=True):
    path: str


class RecipeBinary(RecipeBinaryPath, frozen=True, kw_only=True):
    """`sha256` is optional in the schema so its absence is refused by name, not as a schema error."""

    url: str
    sha256: str | None = None
    member: str | None = None
    then: tuple[str, ...] = ()


##### PACKAGES #####
class RecipeUvName(Struct, frozen=True, kw_only=True):
    name: str


class RecipeUv(RecipeUvName, frozen=True, kw_only=True):
    """`source` carries the pin: `pkg==1.2`, `git+https://…@sha`."""

    source: str


class RecipeNpm(Struct, frozen=True, kw_only=True):
    """`package` carries the pin: `ccusage@20.0.33`."""

    package: str

    @property
    def name(self) -> str:
        """The package without its version: `@scope/pkg@1` → `@scope/pkg`."""
        return self.package if "@" not in self.package[1:] else self.package[: self.package.rindex("@")]


##### CONFIG #####
class RecipeSettings(Struct, frozen=True, kw_only=True):
    """Either `env` (merged under `env`) or `key` (a dotted path) with `value`; uninstall needs `file` only."""

    file: str
    env: dict[str, str] | None = None
    key: str | None = None
    value: Any = None


class RecipeBlock(Struct, frozen=True, kw_only=True):
    file: str
    block: str


class RecipeFile(RecipeBlock, frozen=True, kw_only=True):
    text: str


##### CLAUDE #####
class RecipeMcp(Struct, frozen=True, kw_only=True):
    """stdio needs `command`; http needs `url`. Uninstall reads `name` and `scope` only."""

    name: str
    scope: Literal["user", "project"] = "user"
    transport: Literal["stdio", "http"] = "stdio"
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None


class RecipePlugin(Struct, frozen=True, kw_only=True):
    name: str
    marketplace: str


class RecipePluginSource(RecipePlugin, frozen=True, kw_only=True):
    source: str
