"""services.resolver: wanted ⨝ catalog — which entries a target gets, in an order where every requirement comes first.

A wanted part the catalog does not know is reported, never guessed. A wanted part whose entry serves
another target is dropped. What a kept part `requires` is pulled in even if no source asked for it: an
install order missing its prerequisites is not an order. The whole catalog is ordered once with
`graphlib`, which also proves it acyclic; the wanted closure is read off that order backwards."""

from functools import reduce
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

from e_taxis.models.error import CatalogCycleError, CatalogError
from e_taxis.models.plan import Resolution, Resolved
from e_taxis.models.wanted import WantedPart

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.adapters.ports import CatalogPort, SourcePort
    from e_taxis.models.catalog import Catalog, CatalogEntry, Target


##### TYPES #####
class ResolverService:
    """Joins any SourcePort with the CatalogPort it was given."""

    __slots__ = ("_catalog",)

    def __init__(self, catalog: CatalogPort) -> None:
        self._catalog = catalog

    ##### PRIVATE METHODS #####

    async def _common_load(self) -> Catalog:
        """The catalog, or refused whole: resolving against a catalog that lost files would plan on a lie."""
        catalog = await self._catalog.load()
        match catalog.broken:
            case ():
                return catalog
            case broken:
                msg = f"catalog does not load: {', '.join(name for name, _ in broken)} — run `taxis doctor`"
                raise CatalogError(msg)

    @staticmethod
    def _resolve_order(entries: Mapping[str, CatalogEntry], first: tuple[str, ...]) -> list[str]:
        """Every id in the catalog, requirements first; the wanted ids seed the graph so ties keep their order."""
        graph = {part: entries[part].requires for part in (*first, *entries)}
        try:
            return list(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            raise CatalogCycleError(exc.args[1]) from exc

    @staticmethod
    def _resolve_needed(entries: Mapping[str, CatalogEntry], order: list[str], seeds: set[str]) -> set[str]:
        """Walking the order backwards meets every dependent before what it requires: one pass closes the set."""
        return reduce(
            lambda needed, part: needed | set(entries[part].requires) if part in needed and part in entries else needed,
            reversed(order),
            seeds,
        )

    @staticmethod
    def _resolve_required(entries: Mapping[str, CatalogEntry], chosen: list[str], part: str) -> WantedPart:
        """A part no source asked for, labelled with the first chosen entry that requires it."""
        dependent = next(up for up in chosen if up in entries and part in entries[up].requires)
        return WantedPart(id=part, source=f"requires:{dependent}")

    ############################################################

    ##### PUBLIC #####

    async def listing(self, target: Target | None = None) -> tuple[CatalogEntry, ...]:
        """Every entry, or those serving `target`, in catalog order."""
        catalog = await self._common_load()
        return tuple(entry for entry in catalog.entries if target is None or entry.serves(target))

    async def resolve(self, source: SourcePort, target: Target) -> Resolution:
        entries = {entry.id: entry for entry in (await self._common_load()).entries}
        wanted = await source.wanted(target)
        kept = {part.id: part for part in wanted if part.id in entries and entries[part.id].serves(target)}
        order = self._resolve_order(entries, tuple(kept))
        needed = self._resolve_needed(entries, order, set(kept))
        chosen = [part for part in order if part in needed]
        parts = [kept.get(part) or self._resolve_required(entries, chosen, part) for part in chosen]
        known = [part for part in parts if part.id in entries]
        return Resolution(
            resolved=tuple(
                Resolved(entry=entries[part.id], wanted=part, order=index) for index, part in enumerate(known)
            ),
            unknown=(
                *(part for part in wanted if part.id not in entries),
                *(part for part in parts if part.id not in entries),
            ),
        )
