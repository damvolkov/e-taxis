"""engine.reader: a corpus workflow, read from one e-nous tree, as the graph the executor runs — and a plane graph,
its nodes carded, as the graph the subject executor fans out.

The tree comes from the transpiler's own reader (`GitNous`): every `{source: nodes/<id>.yaml}` envelope is already
resolved there, so no second loader exists. Where things live is what `core/schema.yaml` says: the workflow folder
is its entity path, its port schemas the JSON files under `<folder>/schemas/`, the hooks the files of a config
asset folder named `hooks`. Every node becomes one `StepSpec`; a `loop:` is unrolled into `max` copies so the graph
stays acyclic, and every copy after an ending `until` check stays idle."""

import graphlib
from functools import reduce
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.models.error import PlaneError, WorkflowError
from e_taxis.workflow.models.graph import GraphSpec, LoopDecl, StepSpec
from e_taxis.workflow.models.graphs import GRAPHS
from e_taxis.workflow.models.plane import NodeSpec, PlaneGraph
from e_taxis.workflow.models.workflow import Node, Param, ParamType, Workflow

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.workflow.models.plane import NodeCard, NodeUse, Plane, PlaneDecl, Target

##### DEFAULTS #####
ENTITY: str = "workflow"
AGENT: str = "agent"
HOOKS: str = "hooks"
SCHEMAS: str = "schemas"
BOOLS: frozenset[str] = frozenset({"true", "false"})


##### TYPES #####
class WorkflowReader:
    """The workflows of one tree, decoded and checked against the agents, hooks and schemas that tree holds."""

    __slots__ = ("_tree",)

    def __init__(self, tree: NousTree) -> None:
        self._tree = tree

    ##### PRIVATE METHODS #####

    def _load_models(self, ident: str) -> frozenset[str]:
        """The port models that have a schema: `<workflow folder>/schemas/<Model>.json`."""
        folder = PurePosixPath(self._tree.schema["entities"][ENTITY]["path"].replace("{id}", ident)).parent / SCHEMAS
        return frozenset(
            path.stem
            for blob in self._tree.blobs
            if (path := PurePosixPath(blob)).parent == folder and path.suffix == ".json"
        )

    def _load_hooks(self) -> frozenset[str]:
        return frozenset(
            PurePosixPath(asset).name
            for assets in self._tree.assets.values()
            for asset in assets
            if PurePosixPath(asset).parts[0] == HOOKS
        )

    @staticmethod
    def _read_step(node: Node) -> StepSpec:
        return StepSpec(
            id=node.id,
            depends=node.depends,
            run=node.run,
            actor=node.actor,
            instruction=node.instruction,
            when=node.conditions,
            readonly=node.readonly,
            steps=node.steps,
            timeout=node.timeout,
        )

    @staticmethod
    def _read_copy(
        step: StepSpec,
        k: int,
        loop: LoopDecl,
        *,
        inside: dict[str, tuple[str, ...]],
        exits: tuple[str, ...],
        after: frozenset[str],
    ) -> StepSpec:
        """Iteration `k` of a looped step: in-loop edges stay in the iteration; an entry step of k > 1 also waits on
        the exits of k-1; it names the `until` checks that end it — earlier ones, and its own when it runs after it."""
        looped = frozenset(loop.nodes)
        depends = tuple(f"{d}_{k}" if d in looped else d for d in step.depends)
        entry = tuple(f"{e}_{k - 1}" for e in exits) if k > 1 and not inside[step.id] else ()
        closers = (*(f"{loop.until}_{j}" for j in range(1, k)), *((f"{loop.until}_{k}",) if step.id in after else ()))
        until = step.id == loop.until
        return msgspec.structs.replace(
            step,
            id=f"{step.id}_{k}",
            depends=(*depends, *entry),
            iteration=k,
            until=until,
            previous=f"{loop.until}_{k - 1}" if until and k > 1 else "",
            closers=closers,
        )

    @classmethod
    def _read_unroll(cls, steps: tuple[StepSpec, ...], loop: LoopDecl) -> tuple[StepSpec, ...]:
        """The steps with the loop laid out `max` times; a step outside it that waits on a looped one waits on its
        last copy."""
        looped = frozenset(loop.nodes)
        body = {step.id: step for step in steps if step.id in looped}
        inside = {ident: tuple(d for d in step.depends if d in looped) for ident, step in body.items()}
        order = tuple(graphlib.TopologicalSorter(inside).static_order())
        after = reduce(
            lambda acc, ident: acc | {ident} if set(inside[ident]) & acc else acc, order, frozenset({loop.until})
        ) - {loop.until}
        exits = tuple(ident for ident in order if not any(ident in deps for deps in inside.values()))
        copies = [
            cls._read_copy(body[ident], k, loop, inside=inside, exits=exits, after=after)
            for k in range(1, loop.max + 1)
            for ident in order
        ]
        rest = [
            msgspec.structs.replace(step, depends=tuple(f"{d}_{loop.max}" if d in looped else d for d in step.depends))
            for step in steps
            if step.id not in looped
        ]
        first = next(i for i, step in enumerate(steps) if step.id in looped)
        before = sum(1 for step in steps[:first] if step.id not in looped)
        return (*rest[:before], *copies, *rest[before:])

    ############################################################

    ##### PUBLIC #####

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._tree.entities.get(ENTITY, {})))

    def load(self, ident: str) -> Workflow:
        """The typed workflow, checked against the agents, hooks and schemas the tree holds."""
        match self._tree.entities.get(ENTITY, {}).get(ident):
            case None:
                msg = f"no workflow {ident!r} in {self._tree.root}"
                raise WorkflowError(msg)
            case raw:
                pass
        try:
            decl = msgspec.convert(raw, Workflow)
        except msgspec.ValidationError as bad:
            msg = f"{ident}: {bad}"
            raise WorkflowError(msg) from bad
        match decl.problems(
            frozenset(self._tree.entities.get(AGENT, {})), self._load_hooks(), self._load_models(ident)
        ):
            case ():
                return decl
            case problems:
                msg = f"{ident}: {'; '.join(problems)}"
                raise WorkflowError(msg)

    def read(self, ident: str) -> tuple[GraphSpec, Workflow]:
        """The workflow's executor graph and its typed declaration."""
        decl = self.load(ident)
        steps = tuple(self._read_step(node) for node in decl.nodes)
        unrolled = self._read_unroll(steps, decl.loop) if decl.loop else steps
        return GraphSpec(summary=" ".join(decl.description.split()), steps=unrolled), decl

    def _bind_check(self, name: str, param: Param, value: str) -> str:
        """Why `value` does not fit its parameter's type, or empty: a bool is true or false, an enum one of its values,
        a topic a key of radar.yaml, a path one that exists. Empty is always allowed: the default stands for it."""
        topics = (self._tree.config.get("tekton", {}).get("radar") or {}).get("topics") or {}
        match (param.type, value):
            case (_, ""):
                return ""
            case (ParamType.BOOL, bad) if bad not in BOOLS:
                return f"{name}={bad} is not true or false"
            case (_, bad) if param.values and bad not in param.values:
                return f"{name}={bad} is not one of {', '.join(param.values)}"
            case (ParamType.TOPIC, bad) if bad not in topics:
                return f"{name}={bad} is not a topic of radar.yaml ({', '.join(topics)})"
            case (ParamType.PATH | ParamType.PROJECT, bad) if not Path(bad).expanduser().exists():
                return f"{name}={bad} does not exist"
            case _:
                return ""

    def bind(self, decl: Workflow, given: dict[str, str]) -> dict[str, str]:
        """The run's parameters: only declared names, each checked against its type; the undeclared are refused, the
        omitted take their default."""
        match sorted(set(given) - set(decl.parameters)):
            case []:
                pass
            case unknown:
                msg = f"{decl.id}: undeclared parameter(s) {', '.join(unknown)}"
                raise WorkflowError(msg)
        bound = {name: given.get(name) or param.default for name, param in decl.params.items()}
        match [bad for name, param in decl.params.items() if (bad := self._bind_check(name, param, bound[name]))]:
            case []:
                return bound
            case problems:
                msg = f"{decl.id}: {'; '.join(problems)}"
                raise WorkflowError(msg)


class PlaneReader:
    """The plane graphs (`models.graphs`), each node joined with its own card from `cards` (use → card), and proved
    wired before anything runs: an unknown node, a duplicate id, an unknown dependency or a cycle is refused."""

    __slots__ = ("_cards", "_graphs")

    def __init__(
        self, cards: Mapping[str, NodeCard], graphs: Mapping[Plane, Mapping[Target, PlaneDecl]] = GRAPHS
    ) -> None:
        self._cards = cards
        self._graphs = graphs

    ##### PRIVATE METHODS #####

    def _read_node(self, use: NodeUse) -> NodeSpec:
        match self._cards.get(use.use):
            case None:
                msg = f"{use.key}: no node {use.use!r}"
                raise PlaneError(msg)
            case card:
                return NodeSpec(id=use.key, use=use.use, card=card, depends=use.depends, params=use.params)

    @staticmethod
    def _read_problems(nodes: tuple[NodeSpec, ...]) -> tuple[str, ...]:
        ids = [node.id for node in nodes]
        try:
            graphlib.TopologicalSorter({node.id: node.depends for node in nodes}).prepare()
        except graphlib.CycleError as cycle:
            looped: tuple[str, ...] = (f"cycle: {' → '.join(cycle.args[1])}",)
        else:
            looped = ()
        return (
            *(f"duplicate id {ident}" for ident in sorted({i for i in ids if ids.count(i) > 1})),
            *(f"{node.id} depends on unknown {dep}" for node in nodes for dep in node.depends if dep not in ids),
            *looped,
        )

    ############################################################

    ##### PUBLIC #####

    def targets(self, plane: Plane) -> tuple[Target, ...]:
        """Every target this plane declares a graph for."""
        return tuple(self._graphs[plane])

    def read(self, plane: Plane, target: Target) -> PlaneGraph:
        match self._graphs[plane].get(target):
            case None:
                msg = f"no {plane} graph for {target}"
                raise PlaneError(msg)
            case decl:
                nodes = tuple(self._read_node(use) for use in decl.nodes)
        match self._read_problems(nodes):
            case ():
                return PlaneGraph(plane=plane, target=target, summary=decl.summary, nodes=nodes)
            case problems:
                msg = f"{plane}/{target}: {'; '.join(problems)}"
                raise PlaneError(msg)

    def describe(self, plane: Plane, target: Target | None = None) -> str:
        """Each graph as its nodes in declaration order: role, nature, scope, cadence, edges."""
        graphs = (self.read(plane, one) for one in ((target,) if target else self.targets(plane)))
        return "\n".join(
            f"## {plane}/{graph.target} — {graph.summary}\n"
            + "\n".join(
                f"  {n.id:<20}{n.card.role:<9}{n.card.nature:<15}{n.card.scope:<9}"
                f"{'/'.join(n.card.cadence) or 'always':<15}{'after ' + ', '.join(n.depends) if n.depends else ''}".rstrip()
                for n in graph.nodes
            )
            for graph in graphs
        )
