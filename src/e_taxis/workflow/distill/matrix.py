"""distill.matrix: how much a change weighs, decided by a table and never by a model.

`core/versioning/matrix.yaml` (e-nous) holds the equivalences: the scale, what it costs for an entity to appear or
vanish, and the grade of every slot of every entity. This is only its reader — the part grade needs. The table is
explicit one slot at a time (the same name weighs differently where it lives) and a slot it does not declare
raises instead of defaulting: the corpus grew and the doctrine has not caught up, which is worth a stop."""

from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any, Literal, Self

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import DistillError, UnknownSlotError

if TYPE_CHECKING:
    from pathlib import Path

type Kind = Literal["added", "changed", "removed"]


##### TYPES #####
class MatrixGrade(msgspec.Struct, frozen=True):
    """One step of the scale: its name, its weight, the SemVer bump it forces."""

    name: str
    level: int
    bump: str
    description: str
    example: str = ""


class MatrixLifecycle(msgspec.Struct, frozen=True):
    """What it weighs for a whole entity to appear or to vanish."""

    added: str
    removed: str


class VersionMatrix:
    """The equivalence table, decoded once."""

    __slots__ = ("_grades", "_lifecycle", "_slots", "name")

    def __init__(self, table: dict[str, Any], name: str = "matrix.yaml") -> None:
        self.name = name
        grades = msgspec.convert(table["grades"], tuple[MatrixGrade, ...], strict=False)
        self._grades = tuple(sorted(grades, key=lambda grade: grade.level))
        self._lifecycle = {
            Entity(entity): msgspec.convert(row, MatrixLifecycle, strict=False)
            for entity, row in table["lifecycle"].items()
        }
        self._slots = {Entity(entity): dict(row) for entity, row in table["slots"].items()}

    ##### PRIVATE METHODS #####

    def _of_slot(self, entity: Entity, slot: str) -> str:
        """The grade of one slot, by exact name or by the one family the table admits."""
        declared = self._slots.get(entity, {})
        found = declared.get(slot) or next(
            (g for pattern, g in declared.items() if "*" in pattern and fnmatch(slot, pattern)), None
        )
        match found:
            case str():
                return found
            case _:
                msg = f"{entity}:{slot}: no row of {self.name} judges this slot"
                raise UnknownSlotError(msg)

    ############################################################

    ##### PUBLIC #####

    @classmethod
    async def load(cls, path: Path) -> Self:
        try:
            text = await anyio.Path(path).read_text()
        except FileNotFoundError as missing:
            msg = f"no versioning matrix at {path}"
            raise DistillError(msg) from missing
        return cls(eserde.loads(text, format=eserde.Format.YAML), path.name)

    def __getitem__(self, name: str) -> MatrixGrade:
        """A grade by name; a KeyError, never a StopIteration a caller's generator would eat."""
        match next((grade for grade in self._grades if grade.name == name), None):
            case None:
                msg = f"{name}: no such grade in {self.name}"
                raise KeyError(msg)
            case found:
                return found

    def of(self, entity: Entity, kind: Kind, slots: tuple[str, ...] = ()) -> MatrixGrade:
        """The grade a change carries: the heaviest among its lifecycle and its slots."""
        match kind:
            case "added":
                claimed: tuple[str, ...] = (self._lifecycle[entity].added,)
            case "removed":
                claimed = (self._lifecycle[entity].removed,)
            case _:
                claimed = ()
        names = (*claimed, *(self._of_slot(entity, slot) for slot in slots))
        return max((self[name] for name in names), key=lambda grade: grade.level, default=self._grades[0])
