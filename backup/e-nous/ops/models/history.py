"""models.history — the vocabulary of the corpus history: what changed, when, and how much it weighs.

One module, one concept. Every other module in `history/` speaks these types and
nothing else, so a rename is one edit and the ledger on disk has one schema.

The grades and their bumps are data, not code: they live in `core/versioning/`
and are read by `matrix.py`. Nothing here decides severity — it only carries it.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

import msgspec

from ops.models.entity import Backend, Entity

#: How a path fared between two snapshots.
type Kind = Literal["added", "changed", "removed"]
#: The SemVer step a change forces. `none` means the corpus is untouched.
type Bump = Literal["none", "patch", "minor", "major"]
#: Why a snapshot was taken. A `pre-*` reason is the backup of whatever was there,
#: including edits no transpile made — a plugin's, a runtime's, a hand's.
type Reason = Literal["pre-export", "pre-restore", "export", "manual"]


class Snapshot(msgspec.Struct, frozen=True):
    """A recoverable point in the history. `commit` is the pointer a regression restores to,
    `ref` the name retention releases it by — never rebuilt from the timestamp, which git
    records at second resolution and would collide."""

    commit: str
    at: dt.datetime
    reason: Reason
    note: str = ""
    ref: str = ""

    def __str__(self) -> str:
        return f"{self.commit[:10]} {self.at:%Y-%m-%d %H:%M} {self.reason}{f' · {self.note}' if self.note else ''}"


class FileChange(msgspec.Struct, frozen=True):
    """One path, as the store saw it. The mechanical layer: no entity, no grade."""

    path: str
    kind: Kind

    def __str__(self) -> str:
        return f"{self.kind[0].upper()} {self.path}"


class Change(msgspec.Struct, frozen=True):
    """One path, interpreted: which entity it belongs to, which slots moved, how much it weighs.

    `subentity` is the second axis the corpus already has — a config module
    (`mcp`, `permissions`…), a persona section — and is empty where the id suffices.
    `pointers` are RFC 6901 JSON Pointers into the structured instance: `/description`,
    `/instructions`, `/references/antipatterns.md`.
    """

    entity: Entity
    id: str
    target: str
    kind: Kind
    grade: str = ""
    subentity: str = ""
    pointers: tuple[str, ...] = ()
    summary: str = ""
    review: bool = False

    def __str__(self) -> str:
        where = f"{self.entity}:{self.subentity or self.id}"
        return f"{self.kind[0].upper()} {where} [{self.grade}] {self.summary or self.target}"


class Release(msgspec.Struct, frozen=True):
    """One transpile, recorded. `source` is the repo commit core came from — the bridge
    between the history git keeps of the source and the history this store keeps of the
    harness. `before` is what the target held a moment earlier, recoverable by its commit.
    """

    version: str
    at: dt.datetime
    bump: Bump
    backend: Backend
    target: str
    source: str
    before: Snapshot
    after: Snapshot
    changes: tuple[Change, ...] = ()
    note: str = ""

    @property
    def reviewable(self) -> tuple[Change, ...]:
        """Changes whose graded weight and whose content disagree — the agent's output."""
        return tuple(change for change in self.changes if change.review)


class Retention(msgspec.Struct, frozen=True):
    """When a recovery point may be released. Keeps whichever rule is more generous."""

    keep_last: int = 20
    keep_days: int = 90

    def expired(self, index: int, at: dt.datetime, now: dt.datetime) -> bool:
        """A point is releasable only when it is both beyond the count and beyond the window."""
        return index >= self.keep_last and (now - at).days > self.keep_days
