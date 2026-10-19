"""models.brain: a core projected for one harness, and what installing it would do to the live tree.

A projection is three kinds of change: whole files (paths relative to the tree), owned keys of a shared JSON
file (the harness writes the rest of it), and MCP registrations (held by the harness's own CLI, never a file
the tree holds). A file may be a document: the render owns its declared headings, and every other `## `
section the live file holds is carried after them — nothing live is dropped."""

import re
from enum import StrEnum
from typing import Any, Final

from msgspec import Struct

from e_taxis.models.catalog import Target

##### DEFAULTS #####
H2: Final = re.compile(r"^## (.+?)[ \t]*$", re.MULTILINE)


##### ENUMS #####
class BrainAction(StrEnum):
    """`overwrite` replaces bytes the last install did not write (an edit by hand, or no install on record);
    `orphan` is live in a governed folder and rendered by nothing: reported, never removed."""

    FAITHFUL = "faithful"
    ADD = "add"
    UPDATE = "update"
    OVERWRITE = "overwrite"
    ORPHAN = "orphan"


##### PROJECTION #####
class BrainFile(Struct, frozen=True, kw_only=True):
    """`headings` is set on a document: the `## ` sections the render owns."""

    path: str
    data: bytes
    headings: tuple[str, ...] | None = None

    def merged(self, live: bytes | None) -> bytes:
        """What lands: the render, then every live `## ` section it does not declare."""
        match (self.headings, live):
            case (tuple() as owned, bytes() as found):
                text = found.decode()
                heads = list(H2.finditer(text))
                ends = [*(head.start() for head in heads[1:]), len(text)]
                kept = [
                    "\n\n".join(part for part in (f"## {head.group(1)}", text[head.end() : end].strip("\n")) if part)
                    for head, end in zip(heads, ends, strict=True)
                    if head.group(1) not in owned
                ]
                return self.data + "".join(f"\n\n{part}" for part in kept).encode()
            case _:
                return self.data


class BrainKey(Struct, frozen=True, kw_only=True):
    """One top-level key of a shared JSON file, owned by the render."""

    file: str
    key: str
    value: Any


class BrainServer(Struct, frozen=True, kw_only=True):
    """One MCP registration, in the shape the harness stores it."""

    name: str
    config: dict[str, Any]


class BrainRender(Struct, frozen=True, kw_only=True):
    """`governed` are the folders the render owns whole: anything else in them is an orphan."""

    target: Target
    files: tuple[BrainFile, ...]
    keys: tuple[BrainKey, ...]
    servers: tuple[BrainServer, ...]
    governed: tuple[str, ...]


##### PLAN #####
class BrainMove(Struct, frozen=True, kw_only=True):
    """`path` names a file, `file#key` an owned key, `mcp:name` a registration."""

    path: str
    action: BrainAction


class BrainPlan(Struct, frozen=True, kw_only=True):
    target: Target
    tree: str
    moves: tuple[BrainMove, ...]

    @property
    def pending(self) -> tuple[BrainMove, ...]:
        return tuple(move for move in self.moves if move.action not in {BrainAction.FAITHFUL, BrainAction.ORPHAN})

    def count(self, action: BrainAction) -> int:
        return sum(move.action is action for move in self.moves)
