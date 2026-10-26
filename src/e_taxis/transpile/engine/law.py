"""engine.law: the invariants of `specs/base.yaml` over one validated spec — the closed world, made a gate.

The shape was already checked by the compiled `Spec`; the law checks what a type cannot: that every `from`,
`consumes` and `unmapped` path resolves in the core, that every leaf the core declares for a mapped entity or
module is projected or argued, that destinations, transforms and combinators are declared and used, that a
Markdown block is contiguous and glued one way, that a target which absorbs only carries invertible rows, that a
section exists exactly when the core holds instances. Pure: the spec, the core model and the persona slots in;
findings out."""

from functools import reduce
from itertools import chain, groupby
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.engine.schema import STAR, Leaf
from e_taxis.transpile.models.report import ReportFinding, ReportKind

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from e_taxis.transpile.engine.model import CoreModel, SpecModel

##### DEFAULTS #####
READY: str = "ready"
MARKDOWN: str = "md"
GLUE: str = "\n\n"
NATIVE: str = "native"
MISSING: object = object()


##### TYPES #####
class SpecLaw:
    """The law for one spec: `slots` are the persona slots its facet composes (base + facet)."""

    __slots__ = ("_core", "_model", "_slots", "_spec")

    def __init__(self, spec: Mapping[str, Any], core: CoreModel, model: SpecModel, slots: frozenset[str]) -> None:
        self._spec = spec
        self._core = core
        self._model = model
        self._slots = slots

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_match(left: Leaf, right: Leaf) -> bool:
        """`left` is a prefix of `right`, `*` matching any one segment on either side."""
        return len(left) <= len(right) and all(a == b or STAR in (a, b) for a, b in zip(left, right, strict=False))

    @staticmethod
    def _common_leaf(path: str) -> Leaf:
        return tuple(path.split("."))

    def _common_finding(self, kind: ReportKind, where: str, path: str, detail: str = "") -> ReportFinding:
        return ReportFinding(kind=kind, backend=self._spec["backend"], where=where, path=path, detail=detail)

    def _common_native(self, leaf: Leaf) -> bool:
        found = reduce(
            lambda node, key: node.get(key, MISSING) if isinstance(node, dict) else MISSING,
            leaf[1:],
            self._spec.get("native", {}),
        )
        return found is not MISSING

    def _common_universe(self, name: str, kind: str) -> frozenset[Leaf]:
        match kind:
            case "persona":
                return frozenset((slot,) for slot in self._slots)
            case "instanced":
                return self._core.entity_fields(name)
            case _:
                return self._core.config_leaves(self._spec["harness"])

    def _common_resolves(self, path: str, universe: frozenset[Leaf]) -> bool:
        leaf = self._common_leaf(path)
        match leaf[0]:
            case "native":
                return self._common_native(leaf)
            case _:
                return any(self._common_match(leaf, known) or self._common_match(known, leaf) for known in universe)

    @classmethod
    def _common_via(cls, via: Any) -> tuple[str, ...]:
        """The names a `via` uses: a name, `{name: params}`, or a list of either."""
        match via:
            case str():
                return (via,)
            case dict():
                return tuple(via)
            case list():
                return tuple(name for item in via for name in cls._common_via(item))
            case _:
                return ()

    def _common_target(self, section: Mapping[str, Any], to: str) -> tuple[str, str]:
        target, _, fragment = to.partition("#")
        return (target or section.get("target", ""), fragment)

    def _check_row(
        self, name: str, index: int, section: Mapping[str, Any], row: Mapping[str, Any], universe: frozenset[Leaf]
    ) -> Iterator[ReportFinding]:
        where, transforms = f"{name}[{index}]", self._spec.get("transforms", {})
        target, _ = self._common_target(section, row["to"])
        declared = self._spec["targets"].get(target)
        names = self._common_via(row.get("via"))
        source = row.get("from")
        yield from (
            (self._common_finding(ReportKind.UNDECLARED, where, row["to"], "target declared nowhere"),)
            if declared is None
            else ()
        )
        yield from (
            (self._common_finding(ReportKind.ORPHAN, where, source, "`from` resolves to nothing in core"),)
            if source is not None and not self._common_resolves(source, universe)
            else ()
        )
        yield from (
            self._common_finding(ReportKind.UNDECLARED, where, via, "neither combinator nor transform")
            for via in names
            if via not in self._model.combinators and via not in transforms
        )
        yield from (
            (
                self._common_finding(
                    ReportKind.INVERTIBLE, where, row["to"], "a row on an absorb target must be invertible"
                ),
            )
            if (declared or {}).get("absorb")
            and not all(self._model.combinators.get(via, {}).get("inverse") for via in names)
            else ()
        )

    def _check_cover(self, row: Mapping[str, Any]) -> tuple[Leaf, ...]:
        """What one row covers: a named transform its consumes, a plain row its from."""
        transforms = self._spec.get("transforms", {})
        named = [via for via in self._common_via(row.get("via")) if via in transforms]
        match (named, row.get("from")):
            case ([], None):
                return ()
            case ([], str() as source):
                return (self._common_leaf(source),)
            case _:
                return tuple(self._common_leaf(path) for via in named for path in transforms[via]["consumes"])

    def _check_covers(self, section: Mapping[str, Any]) -> tuple[Leaf, ...]:
        """What the rows and the unmapped entries of a section cover."""
        rows = (leaf for row in section.get("rows", []) for leaf in self._check_cover(row))
        return (*rows, *(self._common_leaf(path) for path in section.get("unmapped", {})))

    def _check_blocks(self, name: str, section: Mapping[str, Any]) -> Iterator[ReportFinding]:
        """Markdown blocks: one run of rows per (target, fragment), one glue per block."""
        keyed = [
            (key, row.get("glue", GLUE))
            for row in section.get("rows", [])
            if self._spec["targets"].get((key := self._common_target(section, row["to"]))[0], {}).get("format")
            == MARKDOWN
        ]
        runs = [(key, {glue for _, glue in group}) for key, group in groupby(keyed, key=lambda item: item[0])]
        keys = [key for key, _ in runs]
        yield from (
            self._common_finding(ReportKind.BLOCK, name, "#".join(key), "the same block twice, not contiguous")
            for key in dict.fromkeys(key for key in keys if keys.count(key) > 1)
        )
        yield from (
            self._common_finding(ReportKind.BLOCK, name, "#".join(key), f"one block, several glues: {sorted(glues)}")
            for key, glues in runs
            if len(glues) > 1
        )

    def _check_section(self, name: str, section: Mapping[str, Any]) -> Iterator[ReportFinding]:
        match (section.get("status", READY) == READY, bool(section.get("rows"))):
            case (True, False):
                yield self._common_finding(ReportKind.INVALID, name, name, "a ready section without rows")
            case (False, True):
                yield self._common_finding(ReportKind.INVALID, name, name, "a pending or retired section with rows")
            case (False, False):
                pass
            case _:
                universe = self._common_universe(name, section["kind"])
                covers = self._check_covers(section)
                yield from chain.from_iterable(
                    self._check_row(name, index, section, row, universe) for index, row in enumerate(section["rows"])
                )
                yield from (
                    self._common_finding(ReportKind.ORPHAN, f"{name}.unmapped", path, "resolves to nothing in core")
                    for path in section.get("unmapped", {})
                    if not self._common_resolves(path, universe)
                )
                yield from self._check_blocks(name, section)
                yield from (
                    self._common_finding(
                        ReportKind.UNCOVERED, name, ".".join(leaf), "in no row, no consumes, no unmapped"
                    )
                    for leaf in sorted(universe)
                    if not any(self._common_match(cover, leaf) for cover in covers)
                )

    def _check_transforms(self) -> Iterator[ReportFinding]:
        used = {
            via
            for section in self._spec["map"].values()
            for row in section.get("rows", [])
            for via in self._common_via(row.get("via"))
        }
        leaves = self._core.config_leaves(self._spec["harness"])
        transforms = self._spec.get("transforms", {})
        yield from (
            self._common_finding(ReportKind.UNUSED, "transforms", name, "declared, used by no row")
            for name in transforms
            if name not in used
        )
        yield from (
            self._common_finding(ReportKind.ORPHAN, f"transforms.{name}", path, "consumes nothing in core")
            for name, transform in transforms.items()
            for path in transform["consumes"]
            if not self._common_resolves(path, leaves)
        )

    def _check_presence(self, instances: Mapping[str, int]) -> Iterator[ReportFinding]:
        """An entity section exists exactly when the facet holds instances of it."""
        facet = self._spec["harness"]
        yield from (
            self._common_finding(
                ReportKind.PRESENCE,
                "map",
                entity,
                "core holds instances, the spec maps nothing" if held else "the spec maps what core never holds",
            )
            for entity, owner in self._core.entities.items()
            if (held := owner == facet and instances.get(entity, 0) > 0) != (entity in self._spec["map"])
        )

    def _check_upstream(self) -> Iterator[ReportFinding]:
        upstream = self._spec["upstream"]
        verified = upstream["verified"].get("version")
        yield from (
            (
                self._common_finding(
                    ReportKind.SIGNAL,
                    "upstream",
                    upstream["version"],
                    f"verified against {verified or 'no version'}: re-check the rows",
                ),
            )
            if verified != upstream["version"]
            else ()
        )

    ############################################################

    ##### PUBLIC #####

    def run(self, instances: Mapping[str, int]) -> tuple[ReportFinding, ...]:
        """Every finding of the spec; `instances` is entity → how many the core holds."""
        match self._spec["harness"] in self._core.facets:
            case False:
                return (
                    self._common_finding(
                        ReportKind.UNDECLARED, "harness", self._spec["harness"], "no such facet in core"
                    ),
                )
            case _:
                return (
                    *chain.from_iterable(
                        self._check_section(name, section) for name, section in self._spec["map"].items()
                    ),
                    *self._check_transforms(),
                    *self._check_presence(instances),
                    *self._check_upstream(),
                )
