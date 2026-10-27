"""models.plane: the evaluator and the enhancer as data — which plane, what runs, over which subjects, after what.

A plane graph names, per target, the nodes it uses (`use`), under which id, after which ids, with which params
(`models.graphs` declares them all). A node describes itself (`NodeCard`: role, nature, scope, guard, cadence); the
graph reader joins the two into `NodeSpec`s the executor fans out over the run's subjects. A run is pinned in a
`PlaneManifest` (the checkout, its HEAD, the tree it measured) and lives under `PlanePaths`. Nothing here runs."""

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path

from msgspec import Struct


##### TYPES #####
class Target(StrEnum):
    """What a graph measures: the corpus alone, one entity kind, or a backend's spec."""

    CORPUS = auto()
    SKILL = auto()
    AGENT = auto()
    COMMAND = auto()
    WORKFLOW = auto()
    TOOL = auto()
    PERSONA = auto()
    CONFIG = auto()
    SPEC = auto()


class Plane(StrEnum):
    """`evaluator` measures and states needs, never writes the source; `enhancer` acts only on a reason, in a sandbox."""

    EVALUATOR = auto()
    ENHANCER = auto()


class Cadence(StrEnum):
    """How often a node is due. A run carries one; a node lists the ones it answers to."""

    COMMIT = auto()
    NIGHTLY = auto()
    WEEKLY = auto()
    MANUAL = auto()


class Role(StrEnum):
    """Why a node exists. Only `propose` varies with the state of the art; gates never do."""

    GATE = auto()
    MEASURE = auto()
    PROPOSE = auto()
    DECIDE = auto()
    EMIT = auto()


class Nature(StrEnum):
    """`deterministic` a pure function of files, zero tokens; `heuristic` sampled model behaviour; `semantic` an agent."""

    DETERMINISTIC = auto()
    HEURISTIC = auto()
    SEMANTIC = auto()


class Scope(StrEnum):
    """Once per run, or once per subject of the target."""

    CORPUS = auto()
    SUBJECT = auto()


class Guard(StrEnum):
    """When a node may run: only over green upstream, or once its upstream settled at all."""

    GREEN = auto()
    SETTLED = auto()


class NodeCard(Struct, frozen=True, kw_only=True):
    """A node's own declaration: intrinsic, graph-independent."""

    role: Role
    summary: str
    nature: Nature = Nature.DETERMINISTIC
    scope: Scope = Scope.SUBJECT
    guard: Guard = Guard.GREEN
    cadence: tuple[Cadence, ...] = ()


class NodeUse(Struct, frozen=True, kw_only=True):
    """One line of a graph: which node, under which id, after which ids, with which params."""

    use: str
    id: str = ""
    depends: tuple[str, ...] = ()
    params: dict[str, str] = {}

    @property
    def key(self) -> str:
        """The graph-unique id: explicit, or the node's own name."""
        return self.id or self.use


class PlaneDecl(Struct, frozen=True, kw_only=True):
    """One plane's graph for one target, as declared."""

    summary: str
    nodes: tuple[NodeUse, ...]


class NodeSpec(Struct, frozen=True, kw_only=True):
    """A node placed in a graph: its card, its use, its edges. What the executor runs."""

    id: str
    use: str
    card: NodeCard
    depends: tuple[str, ...] = ()
    params: dict[str, str] = {}

    def due(self, cadence: Cadence) -> bool:
        """A node that names no cadence is always due; a manual run runs everything."""
        return not self.card.cadence or cadence in self.card.cadence or cadence is Cadence.MANUAL


class PlaneGraph(Struct, frozen=True, kw_only=True):
    """A whole graph in declaration order — the order the report reads it back in."""

    plane: Plane
    target: Target
    summary: str
    nodes: tuple[NodeSpec, ...]

    def __getitem__(self, key: str) -> NodeSpec:
        return next(node for node in self.nodes if node.id == key)

    def __iter__(self) -> Iterator[NodeSpec]:
        return iter(self.nodes)


class PlaneManifest(Struct, frozen=True, kw_only=True):
    """What a run was asked to do and the exact world it did it in.

    `nous` is the checkout and `base_sha` its HEAD; `tree` the source the evaluator measured — the checkout as it
    stands, or the candidate of an enhancer run (`candidate`, its id; `patched` the subjects it changed). `places` is where each subject lives in the
    checkout. `source` is the evaluation an enhancement acts on, `directive` your instruction, `manual` whether your
    working-tree edits are a proposal."""

    run_id: str
    plane: Plane
    target: Target
    subjects: tuple[str, ...]
    cadence: Cadence
    nous: str
    tree: str
    base_sha: str
    backend: str
    started: dt.datetime
    graph: PlaneGraph
    places: dict[str, str] = {}
    source: str = ""
    directive: str = ""
    manual: bool = False
    candidate: str = ""
    patched: tuple[str, ...] = ()

    def place(self, subject: str) -> str:
        """Where a subject lives in the checkout, repo-relative: what is overlaid, diffed and promoted."""
        return self.places[subject]


@dataclass(frozen=True, slots=True)
class PlanePaths:
    """Every place a run writes, all of it under its folder — flat under the reports root, as the workflows that read
    `.reports/<run>/patches/` expect; the run id (`<UTC ms>-<plane>-<target>-<sha7>`) already names plane and target.

        <nous>/.reports/<run>/
          run.json · ledger.jsonl · report.md · report.json
          sandbox/                 the enhancer's clone at the base: the only core/ a run edits
          flat/base/               the render every subject is measured on
          flat/candidate/<id>/     one subject's candidate, rendered from base + its own change
          trees/<id>/              that candidate's source: a clone at the base with the subject's change overlaid
          nodes/<node>/<subject>/  a node's scratch and artifacts
          patches/<target>/<id>.patch"""

    root: Path

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.jsonl"

    @property
    def manifest(self) -> Path:
        return self.root / "run.json"

    @property
    def report(self) -> Path:
        return self.root / "report.md"

    @property
    def sandbox(self) -> Path:
        return self.root / "sandbox"

    @property
    def base(self) -> Path:
        return self.root / "flat" / "base"

    @property
    def patches(self) -> Path:
        return self.root / "patches"

    def candidate(self, subject: str) -> Path:
        return self.root / "flat" / "candidate" / subject

    @property
    def trees(self) -> Path:
        return self.root / "trees"

    def tree(self, subject: str) -> Path:
        return self.trees / subject

    def node(self, node: str, subject: str) -> Path:
        return self.root / "nodes" / node / (subject or "_corpus")
