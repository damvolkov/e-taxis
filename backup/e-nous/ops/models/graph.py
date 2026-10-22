"""models.graph — a graph as data: which plane, what runs, over what, after what.

A graph is declared in markdown (`ops/<plane>/<target>/graph.md`, plane = `eval` or
`enhance`) or built from a corpus workflow (`core/tekton/workflows/<id>/`); each node it uses
describes itself beside its code (`ops/nodes/<area>/<name>/node.md`). Everything decodes
into these types; nothing here executes, reads a file or knows a runner.
"""

from __future__ import annotations

from collections.abc import Collection
from enum import StrEnum, auto

import msgspec


class Target(StrEnum):
    """What a graph evaluates: the corpus alone, one entity kind, or the backend specs."""

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
    """The three planes of ops, plus the corpus workflows the same executor runs.

    `transpiler` renders and records; `evaluator` measures and states needs, never writes
    the source; `enhancer` acts only on an evaluation's needs or an explicit directive;
    `workflow` runs a corpus workflow from `core/tekton/workflows/`.
    """

    TRANSPILER = auto()
    EVALUATOR = auto()
    ENHANCER = auto()
    WORKFLOW = auto()


class Role(StrEnum):
    """Why a node exists. Only `propose` varies with the state of the art; gates never do."""

    GATE = auto()
    MEASURE = auto()
    PROPOSE = auto()
    DECIDE = auto()
    EMIT = auto()


class Nature(StrEnum):
    """How a node reaches its result — the axis the documentation is organized by.

    `deterministic`  a pure function of files: same inputs, same bytes out, zero tokens
    `heuristic`      model behaviour sampled N times and read statistically (routing rate
                     with a Wilson interval, effect Δ with a bootstrap interval)
    `semantic`       an agent reasons and acts (optimizer, integrator, speckeeper)
    """

    DETERMINISTIC = auto()
    HEURISTIC = auto()
    SEMANTIC = auto()

    @property
    def tokens(self) -> bool:
        """Whether a node of this nature spends tokens."""
        return self is not Nature.DETERMINISTIC


class Scope(StrEnum):
    """Once per run, or once per subject of the target."""

    CORPUS = auto()
    SUBJECT = auto()


class Guard(StrEnum):
    """When a node may run: only over green upstream, or once upstream settled at all."""

    GREEN = auto()
    SETTLED = auto()


class Cadence(StrEnum):
    """How often a node is due. A run carries one; a node lists the ones it answers to."""

    COMMIT = auto()
    NIGHTLY = auto()
    WEEKLY = auto()
    MANUAL = auto()


class RunnerKind(StrEnum):
    """The LLM trigger points a node may be served by."""

    CLAUDECODE = auto()
    OPENCODE = auto()
    ANTHROPIC = auto()


class NodeCard(msgspec.Struct, frozen=True, kw_only=True):
    """A node's own declaration, from its `node.md`: intrinsic, graph-independent."""

    role: Role
    summary: str
    nature: Nature = Nature.DETERMINISTIC
    scope: Scope = Scope.SUBJECT
    guard: Guard = Guard.GREEN
    runners: tuple[RunnerKind, ...] = ()
    cadence: tuple[Cadence, ...] = ()


class NodeUse(msgspec.Struct, frozen=True, kw_only=True):
    """One line of a graph file: which node, under which id, after which ids, with which params."""

    use: str
    id: str = ""
    depends: tuple[str, ...] = ()
    params: dict[str, str] = {}

    @property
    def key(self) -> str:
        """The graph-unique id: explicit, or the node's own name."""
        return self.id or self.use.rsplit("/", 1)[-1]


class NodeSpec(msgspec.Struct, frozen=True, kw_only=True):
    """A node placed in a graph: its card, its use, its edges. What the executor runs."""

    id: str
    use: str
    card: NodeCard
    depends: tuple[str, ...] = ()
    params: dict[str, str] = {}

    def due(self, cadence: Cadence) -> bool:
        """A node that names no cadence is always due; otherwise the run's cadence must be listed."""
        return not self.card.cadence or cadence in self.card.cadence or cadence is Cadence.MANUAL


class GraphSpec(msgspec.Struct, frozen=True, kw_only=True):
    """A whole graph, in declaration order — the order the report reads it back in."""

    plane: Plane
    target: Target
    summary: str
    nodes: tuple[NodeSpec, ...]

    def __getitem__(self, key: str) -> NodeSpec:
        return next(node for node in self.nodes if node.id == key)

    def __iter__(self):
        return iter(self.nodes)


class LoopDecl(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """A bounded loop over a run of a workflow's steps: unrolled `max` times, ended by its `until` step.

    The graph never holds a cycle: the executor gets `max` copies (`<id>_<k>`), each copy waiting
    on the previous one's exits, and every copy after an ending `until` check stays idle.
    """

    nodes: tuple[str, ...]
    max: int
    until: str

    def problems(self, ids: Collection[str]) -> tuple[str, ...]:
        """Why this loop cannot be unrolled over a workflow with step `ids`; empty when it can."""
        return (
            *(f"loop: unknown step {node}" for node in self.nodes if node not in ids),
            *((f"loop: until {self.until} is not one of its steps",) if self.until not in self.nodes else ()),
            *(("loop: max must be at least 1",) if self.max < 1 else ()),
        )
