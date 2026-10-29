"""models.workflow: a corpus workflow as typed data — what `core/tekton/workflows/<id>/` declares.

`workflow.yaml` lists its nodes as `{source: nodes/<id>.yaml}`; the e-nous reader resolves the envelopes and
`msgspec` turns the whole into a `Workflow`. A node is one of three kinds, told by what it declares: `run` (a command —
zero tokens), `actor` (that agent's headless session) or neither (the lead's own action). `problems()` is the static
check: an unknown step, agent, hook or port, or a cycle, fails when the workflow is read, before a token is spent."""

import graphlib
from collections.abc import Collection
from enum import StrEnum
from functools import reduce

import msgspec

from e_taxis.workflow.models.graph import LoopDecl


##### UTILITIES #####
def items_workflow(value: str) -> tuple[str, ...]:
    """A list kwarg's items, comma-separated: a name may hold spaces (`auto ontology`), so a space never splits."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


##### TYPES #####
class StepKind(StrEnum):
    """What runs a node: a command, an agent session, or the lead itself."""

    RUN = "run"
    AGENT = "agent"
    LEAD = "lead"


class AgentMode(StrEnum):
    """An agent's `mode` in the live OpenCode tree (absent: `all`) — which driver can run it headless."""

    PRIMARY = "primary"
    SUBAGENT = "subagent"
    ALL = "all"


class ParamType(StrEnum):
    """A parameter's shape; every value still reaches a step as text (`{{name}}`). `project` is a path that, left empty,
    is the git root of the directory the run was launched from; `topic` a key of soa.yaml's topics."""

    STR = "str"
    BOOL = "bool"
    LIST = "list"
    PATH = "path"
    TOPIC = "topic"
    PROJECT = "project"


class Domain(StrEnum):
    """The hemisphere a workflow serves; the transpiler renders it only into that hemisphere's harnesses."""

    TEKTON = "tekton"
    NOMOS = "nomos"


class Param(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One parameter a caller provides. A bare string in the manifest is its `doc`."""

    doc: str = ""
    type: ParamType = ParamType.STR
    default: str = ""
    values: tuple[str, ...] = ()


class Port(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """A typed artifact a node reads or writes: `model` names its schema; an input's `from` is `<node>.<port>`."""

    name: str
    model: str
    origin: str = msgspec.field(default="", name="from")
    max: int = 0


class Trigger(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One way to start the workflow: a CLI line, an `eng` verb, a slash command."""

    cli: str = ""
    eng: str = ""
    slash: str = ""


class Node(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True, omit_defaults=True):
    """One step of the graph, as declared."""

    id: str
    depends: tuple[str, ...] = ()
    when: dict[str, str | tuple[str, ...]] = {}
    run: str = ""
    actor: str = ""
    instruction: str = ""
    readonly: bool = False
    steps: int = 0
    timeout: int = 0
    hooks: tuple[str, ...] = ()
    inputs: tuple[Port, ...] = ()
    outputs: tuple[Port, ...] = ()

    @property
    def kind(self) -> StepKind:
        return StepKind.RUN if self.run else StepKind.AGENT if self.actor else StepKind.LEAD

    @property
    def conditions(self) -> dict[str, tuple[str, ...]]:
        """`when` with every value as a tuple: `{op: update}` and `{op: [update]}` mean the same."""
        return {key: (values,) if isinstance(values, str) else values for key, values in self.when.items()}


class Workflow(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """The manifest with its nodes embedded."""

    id: str
    description: str
    domains: tuple[Domain, ...]
    family: str = ""
    each: str = ""
    parameters: dict[str, str | Param] = {}
    nodes: tuple[Node, ...] = ()
    loop: LoopDecl | None = None
    output: dict[str, str] = {}
    triggers: tuple[Trigger, ...] = ()

    ##### PRIVATE METHODS #####

    def _problems_ancestors(self) -> dict[str, frozenset[str]]:
        """Every step's transitive parents, folded in topological order; a cycle leaves none (the cycle is reported)."""
        parents = {node.id: node.depends for node in self.nodes}
        try:
            order = self.order
        except graphlib.CycleError:
            return {}
        return reduce(
            lambda found, ident: (
                found | {ident: frozenset(parents.get(ident, ())).union(*(found[p] for p in parents.get(ident, ())))}
            ),
            order,
            {},
        )

    def _problems_cycle(self) -> tuple[str, ...]:
        try:
            _ = self.order
        except graphlib.CycleError as cycle:
            return (f"cycle: {' → '.join(cycle.args[1])}",)
        return ()

    ############################################################

    ##### PUBLIC #####

    @property
    def params(self) -> dict[str, Param]:
        return {name: Param(doc=p) if isinstance(p, str) else p for name, p in self.parameters.items()}

    @property
    def order(self) -> tuple[str, ...]:
        """The steps in an order where every parent comes first."""
        return tuple(graphlib.TopologicalSorter({n.id: n.depends for n in self.nodes}).static_order())

    def writers(self, model: str) -> tuple[str, ...]:
        """The steps that write a port of `model`, in declaration order: who answers what a reader expects."""
        return tuple(node.id for node in self.nodes if any(port.model == model for port in node.outputs))

    def problems(
        self, agents: Collection[str], hooks: Collection[str], models: Collection[str] | None = None
    ) -> tuple[str, ...]:
        """Why this workflow cannot run; empty when it can. `models` are the port models with a schema (unchecked when None)."""
        ids = [n.id for n in self.nodes]
        known = set(ids)
        outputs = {f"{n.id}.{p.name}": p.model for n in self.nodes for p in n.outputs}
        ancestors = self._problems_ancestors()
        return (
            *(f"duplicate step {i}" for i in sorted({i for i in ids if ids.count(i) > 1})),
            *(
                [f"each names {self.each!r}, which is no list kwarg"]
                if self.each and getattr(self.params.get(self.each), "type", None) is not ParamType.LIST
                else []
            ),
            *(f"{n.id}: depends on unknown step {d}" for n in self.nodes for d in n.depends if d not in known),
            *(f"{n.id}: unknown agent {n.actor}" for n in self.nodes if n.actor and n.actor not in agents),
            *(f"{n.id}: unknown hook {h}" for n in self.nodes for h in n.hooks if h not in hooks),
            *(f"{n.id}: `run` and `actor` both set" for n in self.nodes if n.run and n.actor),
            *(f"{n.id}: needs `run`, `actor` or `instruction`" for n in self.nodes if not (n.run or n.instruction)),
            *(
                f"{n.id}: `when` names undeclared parameter {k}"
                for n in self.nodes
                for k in n.when
                if k not in self.parameters
            ),
            *(
                f"{n.id}: input {p.name} reads {p.origin}, which no ancestor writes"
                for n in self.nodes
                for p in n.inputs
                if p.origin
                and (p.origin not in outputs or p.origin.split(".")[0] not in ancestors.get(n.id, frozenset()))
            ),
            *(
                f"{n.id}: input {p.name} expects {p.model}, {p.origin} writes {outputs[p.origin]}"
                for n in self.nodes
                for p in n.inputs
                if p.origin in outputs and outputs[p.origin] != p.model
            ),
            *(self.loop.problems(known) if self.loop else ()),
            *(
                f"{n.id}: port {p.name} names model {p.model}, which has no schema"
                for n in self.nodes
                for p in (*n.inputs, *n.outputs)
                if models is not None and p.model not in models
            ),
            *self._problems_cycle(),
        )
