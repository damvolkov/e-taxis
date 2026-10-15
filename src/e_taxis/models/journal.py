"""models.journal: one recorded run — every store key it wrote, and every change it made to the world.

`writes` are the store's own keys, with the value each held before. `effects` are what the primitives did
outside the store — a file placed, a JSON key set, a marked block written, a CLI registration — each
carrying exactly what undo needs to put it back. Effects are tagged by `kind` in JSON."""

from datetime import datetime
from typing import Any

from msgspec import Struct


##### EFFECTS #####
class JournalFile(Struct, frozen=True, kw_only=True, tag_field="kind", tag="file"):
    """A whole file written or removed: `before` is None where the run created it, `mode` its prior bits."""

    path: str
    before: bytes | None
    mode: int | None = None


class JournalKey(Struct, frozen=True, kw_only=True, tag_field="kind", tag="key"):
    """One JSON key: `created` counts the trailing segments of `path` the run made (0: it held `before`);
    `fresh` says the run created the file itself."""

    file: str
    path: tuple[str, ...]
    before: Any = None
    created: int = 0
    fresh: bool = False


class JournalBlock(Struct, frozen=True, kw_only=True, tag_field="kind", tag="block"):
    """One marked block of a text file: `before` is its prior body, None where the run inserted it."""

    file: str
    block: str
    before: str | None
    fresh: bool = False


class JournalCommand(Struct, frozen=True, kw_only=True, tag_field="kind", tag="command"):
    """A CLI registration: the argv that ran, and the argv that reverses it."""

    argv: tuple[str, ...]
    undo: tuple[str, ...]


type JournalEffect = JournalFile | JournalKey | JournalBlock | JournalCommand


##### TYPES #####
class Journal(Struct, frozen=True, kw_only=True):
    """What undo needs to put the store and the world back: `before` is None where the run created the key.

    `id` is the run's nanosecond clock, zero-padded, so journal keys sort in the order the runs happened."""

    id: str
    command: str
    at: datetime
    writes: tuple[tuple[str, bytes | None], ...]
    effects: tuple[JournalEffect, ...] = ()
