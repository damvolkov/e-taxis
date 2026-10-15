"""models.primitive: what one primitive is told and what it answers — the run's context in, its changes out.

A primitive reads paths as the catalog writes them (`~/.local/bin/bd`); the context resolves them against
the run's home, and `~/.claude` against Claude Code's config dir (CLAUDE_CONFIG_DIR when set), so a test or
a sandboxed run never reaches the real one."""

from pathlib import Path

from msgspec import Struct

from e_taxis.models.catalog import Primitive, Target
from e_taxis.models.journal import JournalEffect


##### TYPES #####
class PrimitiveContext(Struct, frozen=True, kw_only=True):
    """`update` says the part is present off its pin: a primitive that cannot overwrite in place clears first."""

    target: Target
    home: Path
    claude: Path
    update: bool = False

    def expand(self, raw: str) -> Path:
        match Path(raw).parts:
            case ("~", ".claude", *rest):
                return self.claude.joinpath(*rest)
            case ("~", *rest):
                return self.home.joinpath(*rest)
            case _:
                return Path(raw)


class PrimitiveStep(Struct, frozen=True, kw_only=True):
    """Done: every change made, in the order made, and a line for the report."""

    effects: tuple[JournalEffect, ...] = ()
    detail: str = ""


class NotSupportedYet(Struct, frozen=True, kw_only=True):
    """A primitive this phase does not write: nothing was changed."""

    primitive: Primitive
    detail: str


type PrimitiveResult = PrimitiveStep | NotSupportedYet
