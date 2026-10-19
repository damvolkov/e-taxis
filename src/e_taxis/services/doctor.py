"""services.doctor: catalog integrity — every file parses, ids are unique, `requires` resolve and form a DAG,
each recipe's primitive can serve the targets it is keyed for, and no config key has two owners.

A recipe keyed `any` serves every target its entry lists, so its primitive must serve them all: a
`claude-mcp` recipe cannot install an OpenCode MCP. `system` is harness-independent: no harness primitive."""

from collections import Counter
from graphlib import CycleError, TopologicalSorter
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from e_taxis.models.catalog import Primitive, RecipeKey, Target
from e_taxis.models.doctor import DoctorProblem, DoctorReport, DoctorRule

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.adapters.ports import CatalogPort
    from e_taxis.models.catalog import CatalogEntry

##### DEFAULTS #####
EVERY: Final[frozenset[Target]] = frozenset(Target)
HARNESSES: Final[frozenset[Target]] = EVERY - {Target.SYSTEM}
SERVES: Final[Mapping[Primitive, frozenset[Target]]] = MappingProxyType(
    {
        Primitive.UV_TOOL: EVERY,
        Primitive.NPM: EVERY,
        Primitive.BINARY: EVERY,
        Primitive.COMPOSE: EVERY,
        Primitive.FILE: EVERY,
        Primitive.ENV: EVERY,
        Primitive.SETTINGS: HARNESSES,
        Primitive.CLAUDE_PLUGIN: frozenset({Target.CLAUDECODE}),
        Primitive.CLAUDE_MCP: frozenset({Target.CLAUDECODE}),
    }
)


##### TYPES #####
class DoctorService:
    """Reads the catalog through its port and checks it whole; reports, never raises."""

    __slots__ = ("_catalog",)

    def __init__(self, catalog: CatalogPort) -> None:
        self._catalog = catalog

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_duplicates(entries: tuple[CatalogEntry, ...]) -> list[DoctorProblem]:
        counts = Counter(entry.id for entry in entries)
        return [
            DoctorProblem(rule=DoctorRule.DUPLICATE, id=part, detail=f"{count} entries")
            for part, count in counts.items()
            if count > 1
        ]

    @staticmethod
    def _run_requires(entries: tuple[CatalogEntry, ...]) -> list[DoctorProblem]:
        ids = {entry.id for entry in entries}
        return [
            DoctorProblem(rule=DoctorRule.REQUIRES, id=entry.id, detail=f"requires {part}, which no entry provides")
            for entry in entries
            for part in entry.requires
            if part not in ids
        ]

    @staticmethod
    def _run_cycle(entries: tuple[CatalogEntry, ...]) -> list[DoctorProblem]:
        try:
            TopologicalSorter({entry.id: entry.requires for entry in entries}).prepare()
        except CycleError as exc:
            cycle: list[str] = exc.args[1]
            return [DoctorProblem(rule=DoctorRule.CYCLE, id=min(cycle), detail=" → ".join(cycle))]
        else:
            return []

    @staticmethod
    def _run_primitives(entries: tuple[CatalogEntry, ...]) -> list[DoctorProblem]:
        return [
            DoctorProblem(
                rule=DoctorRule.PRIMITIVE,
                id=entry.id,
                detail=f"{recipe.primitive} under `{key}` cannot serve {target}",
            )
            for entry in entries
            for key, recipe in entry.recipes.items()
            for target in (entry.targets if key is RecipeKey.ANY else (Target(key),))
            if target not in SERVES[recipe.primitive]
        ]

    @staticmethod
    def _run_owns(entries: tuple[CatalogEntry, ...]) -> list[DoctorProblem]:
        owners = Counter(key for entry in entries for key in set(entry.owns))
        return [
            DoctorProblem(
                rule=DoctorRule.OWNS,
                id=key,
                detail=f"owned by {', '.join(entry.id for entry in entries if key in entry.owns)}",
            )
            for key, count in owners.items()
            if count > 1
        ]

    ############################################################

    ##### PUBLIC #####

    async def run(self) -> DoctorReport:
        catalog = await self._catalog.load()
        entries = catalog.entries
        return DoctorReport(
            checked=len(entries),
            problems=(
                *(DoctorProblem(rule=DoctorRule.PARSE, id=name, detail=reason) for name, reason in catalog.broken),
                *self._run_duplicates(entries),
                *self._run_requires(entries),
                *self._run_cycle(entries),
                *self._run_primitives(entries),
                *self._run_owns(entries),
            ),
        )
