"""services.check: an e-nous checkout held to its own law — the gate every transpile passes before it renders.

One read of the checkout; both schemas compiled from it; every core instance and every spec validated against
them (closed world: an undeclared field is a finding, never a silent pass); a persona slot declared by two layers
of one facet refused; then the law of each spec. The report is stamped with the commit and every spec's version.
Nothing is written."""

from collections import Counter
from itertools import chain
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.engine.law import SpecLaw
from e_taxis.transpile.engine.model import CoreModel, SpecModel
from e_taxis.transpile.models.error import SchemaError
from e_taxis.transpile.models.report import CORE, Report, ReportFinding, ReportKind, ReportStamp

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import NousPort

##### DEFAULTS #####
UNKNOWN: str = "?"


##### TYPES #####
class CheckService:
    """Stateless: the checkout comes in through its port on every call."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_valid(backend: str, where: str, check: Callable[[], Any]) -> tuple[ReportFinding, ...]:
        """No finding when `check` passes; one `invalid` finding with the failing path when it raises."""
        try:
            check()
        except SchemaError as exc:
            return (
                ReportFinding(kind=ReportKind.INVALID, backend=backend, where=where, path=where, detail=exc.message),
            )
        return ()

    @staticmethod
    def _run_slots(tree: NousTree, facet: str, layers: tuple[str, ...]) -> Iterator[ReportFinding]:
        counted = Counter(slot for layer in layers for slot in tree.persona[layer].get("slots", {}))
        yield from (
            ReportFinding(
                kind=ReportKind.INVALID,
                backend=CORE,
                where=f"persona/{facet}",
                path=slot,
                detail="declared by two layers",
            )
            for slot, seen in counted.items()
            if seen > 1
        )

    @classmethod
    def _run_core(cls, tree: NousTree, core: CoreModel) -> Iterator[ReportFinding]:
        yield from chain.from_iterable(
            cls._run_valid(
                CORE,
                f"persona/{layer}",
                lambda facet=facet, layer=layer: core.check_persona(facet, tree.persona[layer]),
            )
            for facet, layers in core.facets.items()
            for layer in layers
        )
        yield from chain.from_iterable(cls._run_slots(tree, facet, layers) for facet, layers in core.facets.items())
        yield from chain.from_iterable(
            cls._run_valid(
                CORE,
                f"config/{facet}/{module}",
                lambda facet=facet, module=module, content=content: core.check_module(facet, module, content),
            )
            for facet, modules in tree.config.items()
            for module, content in modules.items()
        )
        yield from chain.from_iterable(
            cls._run_valid(
                CORE, f"{entity}/{ident}", lambda entity=entity, manifest=manifest: core.check_entity(entity, manifest)
            )
            for entity, instances in tree.entities.items()
            for ident, manifest in instances.items()
        )

    @classmethod
    def _run_spec(
        cls, tree: NousTree, core: CoreModel, model: SpecModel, key: str, spec: Mapping[str, Any]
    ) -> tuple[ReportFinding, ...]:
        """The shape first: a spec its type refuses gets no law, which would only read a broken shape."""
        match cls._run_valid(key.rpartition("/")[2], "spec", lambda: model.check(spec)):
            case ():
                layers = core.facets.get(spec["harness"], ())
                slots = frozenset(slot for layer in layers for slot in tree.persona.get(layer, {}).get("slots", {}))
                instances = {entity: len(found) for entity, found in tree.entities.items()}
                return SpecLaw(spec, core, model, slots).run(instances)
            case refused:
                return refused

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def stamp(tree: NousTree, model: str) -> ReportStamp:
        """What a report versions: the checkout, the commit read, the model, every spec's model version."""
        return ReportStamp(
            root=tree.root,
            commit=tree.commit,
            model=model,
            specs={key.rpartition("/")[2]: str(spec.get("spec", UNKNOWN)) for key, spec in tree.specs.items()},
        )

    async def run(self, nous: NousPort) -> Report:
        tree = await nous.load()
        try:
            core, model = CoreModel(tree.schema), SpecModel(tree.base)
        except SchemaError as exc:
            finding = ReportFinding(
                kind=ReportKind.INVALID, backend=CORE, where="schema", path="schema", detail=exc.message
            )
            return Report(
                stamp=ReportStamp(root=tree.root, commit=tree.commit, model=UNKNOWN, specs={}), findings=(finding,)
            )
        stamp = self.stamp(tree, model.version)
        specs = chain.from_iterable(self._run_spec(tree, core, model, key, spec) for key, spec in tree.specs.items())
        return Report(stamp=stamp, findings=(*self._run_core(tree, core), *specs))
