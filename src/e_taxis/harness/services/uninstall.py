"""services.uninstall: one part taken out through its entry's `uninstall` recipe — with --cascade, every entry that
requires it first, dependents before what they depend on.

Each part is probed: an absent part is left alone, a part this phase does not write is `deferred`, and
without `write` the rest are only `planned`. An uninstall recipe whose primitive is not the one the target
installs through is refused: the catalog has one uninstall per entry, and for a target that installs another
way it would reverse the wrong thing. The first failure stops the run; every change is recorded for undo."""

import asyncio
from functools import reduce
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

from e_taxis.harness.models.error import CatalogCycleError, PrimitiveError, UninstallError
from e_taxis.harness.models.primitive import NotSupportedYet, PrimitiveContext
from e_taxis.harness.models.uninstall import UninstallReport, UninstallStatus, UninstallStep

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from e_taxis.harness.models.catalog import CatalogEntry, Primitive, Target
    from e_taxis.harness.models.plan import Probe
    from e_taxis.harness.models.ports import PrimitivePort, ProbePort, RecorderPort
    from e_taxis.harness.services.resolver import ResolverService


##### TYPES #####
class UninstallService:
    """Resolver for the entries serving the target, ProbePort for what is there, the primitive table, the recorder."""

    __slots__ = ("_claude", "_home", "_primitives", "_probe", "_recorder", "_resolver")

    def __init__(
        self,
        resolver: ResolverService,
        probe: ProbePort,
        primitives: Mapping[Primitive, PrimitivePort],
        recorder: RecorderPort,
        *,
        home: Path,
        claude: Path,
    ) -> None:
        self._resolver = resolver
        self._probe = probe
        self._primitives = primitives
        self._recorder = recorder
        self._home = home
        self._claude = claude

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_order(entries: Mapping[str, CatalogEntry], part: str, *, cascade: bool) -> list[str]:
        """`part` alone, or `part` and every transitive dependent — dependents first."""
        graph = {key: tuple(need for need in entry.requires if need in entries) for key, entry in entries.items()}
        try:
            order = list(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            raise CatalogCycleError(exc.args[1]) from exc
        ### forward, every requirement is met before its dependents: one pass closes the dependent set.
        chosen = (
            reduce(lambda found, key: found | {key} if found & set(graph[key]) else found, order, {part})
            if cascade
            else {part}
        )
        return [key for key in reversed(order) if key in chosen]

    async def _run_remove(self, entry: CatalogEntry, target: Target) -> UninstallStep:
        ctx = PrimitiveContext(target=target, home=self._home, claude=self._claude)
        installer = entry.recipe(target)
        match entry.uninstall:
            case None:
                return UninstallStep(id=entry.id, status=UninstallStatus.FAILED, detail="no uninstall recipe")
            case recipe if installer is None or installer.primitive is not recipe.primitive:
                via = installer.primitive if installer else "nothing"
                detail = f"uninstall recipe is {recipe.primitive}, {target} installs through {via}"
                return UninstallStep(id=entry.id, status=UninstallStatus.FAILED, detail=detail)
            case recipe:
                try:
                    result = await self._primitives[recipe.primitive].uninstall(entry, recipe, ctx)
                except PrimitiveError as exc:
                    self._recorder.record(*exc.effects)
                    return UninstallStep(id=entry.id, status=UninstallStatus.FAILED, detail=exc.message)
                except OSError as exc:
                    return UninstallStep(id=entry.id, status=UninstallStatus.FAILED, detail=str(exc))
        match result:
            case NotSupportedYet(detail=detail):
                return UninstallStep(id=entry.id, status=UninstallStatus.DEFERRED, detail=detail)
            case done:
                self._recorder.record(*done.effects)
                return UninstallStep(id=entry.id, status=UninstallStatus.REMOVED, detail=done.detail)

    async def _run_step(self, entry: CatalogEntry, probe: Probe, target: Target, *, write: bool) -> UninstallStep:
        match (probe.present, entry.deferral(target), write):
            case (False, _, _):
                return UninstallStep(id=entry.id, status=UninstallStatus.ABSENT, detail=probe.detail)
            case (True, str() as deferred, _):
                return UninstallStep(id=entry.id, status=UninstallStatus.DEFERRED, detail=deferred)
            case (True, None, False):
                return UninstallStep(id=entry.id, status=UninstallStatus.PLANNED, detail=probe.detail)
            case _:
                return await self._run_remove(entry, target)

    ############################################################

    ##### PUBLIC #####

    async def run(self, part: str, target: Target, *, cascade: bool, write: bool) -> UninstallReport:
        entries = {entry.id: entry for entry in await self._resolver.listing(target)}
        match part in entries:
            case False:
                msg = f"no entry {part} serves {target}"
                raise UninstallError(msg)
            case _:
                pass
        order = self._run_order(entries, part, cascade=cascade)
        probes = await asyncio.gather(*(self._probe.run(entries[key].probe) for key in order))
        steps: list[UninstallStep] = []
        ### sequential on purpose: a dependent goes before what it depends on.
        for key, probe in zip(order, probes, strict=True):
            halted = bool(steps) and steps[-1].status in {UninstallStatus.FAILED, UninstallStatus.NOT_RUN}
            steps.append(
                UninstallStep(id=key, status=UninstallStatus.NOT_RUN, detail="an earlier step failed")
                if halted
                else await self._run_step(entries[key], probe, target, write=write)
            )
        return UninstallReport(target=target, steps=tuple(steps))
