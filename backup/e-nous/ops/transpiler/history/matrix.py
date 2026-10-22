"""transpiler.history.matrix — how much a change weighs, decided by a table and never by a model.

`core/versioning/matrix.yaml` holds the equivalences: the scale, what it costs for an
entity to appear or vanish, and the grade of every slot of every entity. This module
is only its reader. Severity stays mechanical on purpose — an agent able to raise or
lower a version would turn a deterministic pipeline into a persuadable one.

The table is explicit one slot at a time rather than pattern-matched, because the same
name weighs differently depending on where it lives: `instructions` in a skill is the
body that governs conduct; `instructions` in config is the list of files the coder
loads at boot. A slot the table does not declare raises instead of defaulting to
patch — the corpus grew and the doctrine has not caught up, which is worth a stop.
"""

from __future__ import annotations

from fnmatch import fnmatch
from functools import cached_property
from pathlib import Path
from typing import Final

import eserde
import msgspec

from ops.core.settings import settings
from ops.models.entity import Entity
from ops.models.history import Bump, Kind

#: The table, in core: doctrine of the house, not corpus the harness loads.
MATRIX_FILE: Final[Path] = Path("core/versioning/matrix.yaml")
#: SemVer steps, weakest first — the order that makes `max` mean "the heaviest".
WEIGHT: Final[tuple[Bump, ...]] = ("none", "patch", "minor", "major")


class UnknownSlotError(KeyError):
    """A slot no row of the matrix judges. The table is behind the corpus."""


class Grade(msgspec.Struct, frozen=True):
    """One step of the scale: what it is called, what it costs, and why it exists."""

    name: str
    level: int
    bump: Bump
    description: str
    example: str = ""


class Lifecycle(msgspec.Struct, frozen=True):
    """What it weighs for a whole entity to appear or to vanish."""

    added: str
    removed: str


class Matrix:
    """The equivalence table. One instance reads it once."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.ROOT / MATRIX_FILE

    # ---------------------------------------------------------------- public
    @cached_property
    def grades(self) -> tuple[Grade, ...]:
        """Every step of the scale, lightest first."""
        return tuple(
            sorted(
                msgspec.convert(self._table["grades"], tuple[Grade, ...], strict=False), key=lambda grade: grade.level
            )
        )

    @cached_property
    def lifecycle(self) -> dict[Entity, Lifecycle]:
        """Per entity, the grade of appearing and of vanishing."""
        return {
            Entity(name): msgspec.convert(row, Lifecycle, strict=False)
            for name, row in self._table["lifecycle"].items()
        }

    @cached_property
    def slots(self) -> dict[Entity, dict[str, str]]:
        """Per entity, every slot the corpus may emit and the grade it carries."""
        return {Entity(name): dict(row) for name, row in self._table["slots"].items()}

    def of(self, entity: Entity, kind: Kind, slots: tuple[str, ...] = ()) -> Grade:
        """The grade a change carries: the heaviest verdict among its lifecycle and its slots.

        A change weighs what its worst slot weighs; an entity that appeared or vanished
        weighs that on its own, whatever its slots say.
        """
        claimed = (
            [self[self.lifecycle[entity].added if kind == "added" else self.lifecycle[entity].removed]]
            if kind != "changed"
            else []
        )
        claimed += [self[self._slot(entity, slot)] for slot in slots]
        return max(claimed, key=lambda grade: grade.level, default=self.grades[0])

    def bump(self, grades: tuple[str, ...]) -> Bump:
        """The SemVer step a set of graded changes forces. No change, no step."""
        return max((self[name].bump for name in grades), key=WEIGHT.index, default="none")

    def declared(self, entity: Entity) -> frozenset[str]:
        """Every slot of an entity the table judges — what a coverage gate compares against."""
        return frozenset(self.slots.get(entity, {}))

    def __getitem__(self, name: str) -> Grade:
        """A grade by name. Raises KeyError, never StopIteration — a caller's generator would eat that."""
        if (found := next((grade for grade in self.grades if grade.name == name), None)) is None:
            raise KeyError(f"{name}: no such grade in {self.path.name}")
        return found

    # --------------------------------------------------------------- private
    @cached_property
    def _table(self) -> dict:
        return eserde.load(self.path)

    def _slot(self, entity: Entity, slot: str) -> str:
        """The grade of one slot, by exact name or by the one family the table admits."""
        declared = self.slots.get(entity, {})
        if (exact := declared.get(slot)) is not None:
            return exact
        if family := next((g for pattern, g in declared.items() if "*" in pattern and fnmatch(slot, pattern)), None):
            return family
        raise UnknownSlotError(f"{entity}:{slot}: no row of {self.path.name} judges this slot")
