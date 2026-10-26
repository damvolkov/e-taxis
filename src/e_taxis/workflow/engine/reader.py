"""engine.reader: a corpus workflow, read from one e-nous tree, as the graph the executor runs.

The tree comes from the transpiler's own reader (`GitNous`): every `{source: nodes/<id>.yaml}` envelope is already
resolved there, so no second loader exists. Where things live is what `core/schema.yaml` says: the workflow folder
is its entity path, its port schemas the JSON files under `<folder>/schemas/`, the hooks the files of a config
asset folder named `hooks`. Every node becomes one `StepSpec`; a `loop:` is unrolled into `max` copies so the graph
stays acyclic, and every copy after an ending `until` check stays idle."""

import graphlib
from functools import reduce
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.models.error import WorkflowError
from e_taxis.workflow.models.graph import GraphSpec, LoopDecl, StepSpec
from e_taxis.workflow.models.workflow import Node, Workflow

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree

##### DEFAULTS #####
ENTITY: str = "workflow"
AGENT: str = "agent"
HOOKS: str = "hooks"
SCHEMAS: str = "schemas"


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

    @staticmethod
    def bind(decl: Workflow, given: dict[str, str]) -> dict[str, str]:
        """The run's parameters: only declared names; the undeclared are refused, the omitted take their default."""
        match sorted(set(given) - set(decl.parameters)):
            case []:
                return {name: given.get(name, param.default) for name, param in decl.params.items()}
            case unknown:
                msg = f"{decl.id}: undeclared parameter(s) {', '.join(unknown)}"
                raise WorkflowError(msg)
