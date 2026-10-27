"""engine.executor: the graph manager — graphlib checks the order, one TaskGroup runs, the ledger remembers.

Every step becomes one task of a single TaskGroup that waits only for its own upstream: a step starts the moment
its dependencies ended, never at a wave boundary, so independent branches overlap. One Semaphore bounds the run.

A step never takes the run down. An exception becomes an `error` outcome, a red upstream a `skip` — all recorded.
The executor is the only writer of the ledger, and `notify` hears each record as it lands. A step whose inputs did
not move since the ledger last recorded it (same input hash, not an error) is not paid for twice.

graphlib, not rustworkx: the order of a dozen steps is no hot path, and graphlib is already this repo's DAG tool.

The planes (evaluator, enhancer) run on `SubjectExecutor`: the same shape keyed (node, subject), its nodes found by
their `use` in a table — the second node kind the workflow executor's one-node injection anticipated."""

import asyncio
import datetime as dt
import graphlib
import hashlib
from typing import TYPE_CHECKING, Final

import msgspec

from e_taxis.workflow.models.error import WorkflowError
from e_taxis.workflow.models.plane import Guard, Scope
from e_taxis.workflow.models.ports import NodeContext, PlaneContext
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.graph import StepSpec
    from e_taxis.workflow.models.plane import NodeSpec
    from e_taxis.workflow.models.ports import NodePort, PlaneNodePort, PlaneState, RunState

##### DEFAULTS #####
ENCODER: Final[msgspec.json.Encoder] = msgspec.json.Encoder(order="deterministic")
REASON: int = 2000


##### TYPES #####
class DagExecutor:
    """Runs `state.manifest.graph` and returns every step run it recorded, in declaration order.

    One node kind exists (a workflow step), so the node is injected whole; a second kind would make this a frozen
    table use → node."""

    __slots__ = ("_concurrency", "_node", "_notify")

    def __init__(self, node: NodePort, concurrency: int, notify: Callable[[NodeRun], None] | None = None) -> None:
        self._node = node
        self._concurrency = concurrency
        self._notify = notify or (lambda _: None)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_check(state: RunState) -> None:
        try:
            graphlib.TopologicalSorter({step.id: step.depends for step in state.manifest.graph}).prepare()
        except graphlib.CycleError as cycle:
            msg = f"{state.manifest.workflow}: cycle through {' → '.join(cycle.args[1])}"
            raise WorkflowError(msg) from cycle

    @staticmethod
    def _run_upstream(state: RunState, spec: StepSpec) -> tuple[NodeRun, ...]:
        return tuple(run for dep in spec.depends if (run := state.ledger.latest(dep)) is not None)

    @staticmethod
    def _run_hash(state: RunState, spec: StepSpec, upstream: tuple[NodeRun, ...]) -> str:
        payload = (spec, state.manifest.base_sha, state.manifest.params, sorted(run.output_hash for run in upstream))
        return hashlib.sha256(ENCODER.encode(payload)).hexdigest()

    @staticmethod
    def _run_gate(upstream: tuple[NodeRun, ...]) -> Outcome | None:
        """The outcome a step gets without running — a red upstream skips it — or None when it must run."""
        match next((run for run in upstream if not run.status.green), None):
            case NodeRun() as red:
                return Outcome(status=Status.SKIP, reason=f"upstream {red.node} is {red.status}")
            case _:
                return None

    @staticmethod
    def _run_kept(state: RunState, spec: StepSpec, digest: str) -> NodeRun | None:
        match state.ledger.latest(spec.id):
            case NodeRun(input_hash=seen, status=status) as kept if seen == digest and status is not Status.ERROR:
                return kept
            case _:
                return None

    async def _run_call(self, state: RunState, spec: StepSpec, gate: asyncio.Semaphore) -> Outcome:
        """The step itself, bounded; any exception is a recorded `error`, never a crashed run."""
        async with gate:
            try:
                return await self._node.run(NodeContext(state=state, spec=spec))
            except Exception as exc:  # noqa: BLE001 — a step's failure is evidence, not a crash
                return Outcome(status=Status.ERROR, reason=f"{type(exc).__name__}: {exc}"[:REASON])

    async def _run_fresh(
        self, state: RunState, spec: StepSpec, gate: asyncio.Semaphore, digest: str, upstream: tuple[NodeRun, ...]
    ) -> NodeRun:
        started = dt.datetime.now(dt.UTC)
        outcome = self._run_gate(upstream) or await self._run_call(state, spec, gate)
        run = NodeRun(
            run_id=state.manifest.run_id,
            node=spec.id,
            status=outcome.status,
            started=started,
            ended=dt.datetime.now(dt.UTC),
            input_hash=digest,
            output_hash=hashlib.sha256(ENCODER.encode(outcome)).hexdigest(),
            metrics=outcome.metrics,
            reason=outcome.reason,
            tokens=outcome.tokens,
            cached=outcome.cached,
            runner=outcome.runner,
            artifacts=outcome.artifacts,
        )
        await state.ledger.append(run)
        self._notify(run)
        return run

    async def _run_ready(
        self, state: RunState, spec: StepSpec, gate: asyncio.Semaphore, events: dict[str, asyncio.Event]
    ) -> NodeRun:
        """Wait for this step's own upstream, run it, then release its dependents — even on error."""
        try:
            await asyncio.gather(*(events[dep].wait() for dep in spec.depends))
            upstream = self._run_upstream(state, spec)
            digest = self._run_hash(state, spec, upstream)
            return self._run_kept(state, spec, digest) or await self._run_fresh(state, spec, gate, digest, upstream)
        finally:
            events[spec.id].set()

    ############################################################

    ##### PUBLIC #####

    async def run(self, state: RunState) -> tuple[NodeRun, ...]:
        """Every step as one task that starts when its own upstream ended, under one bound."""
        self._run_check(state)
        gate = asyncio.Semaphore(self._concurrency)
        events = {spec.id: asyncio.Event() for spec in state.manifest.graph}
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(self._run_ready(state, spec, gate, events)) for spec in state.manifest.graph]
        return tuple(task.result() for task in tasks)


class SubjectExecutor:
    """Runs a plane graph: every (node, subject) pair is one task — a subject-scoped node fans out over the run's subjects,
    a corpus-scoped one runs once — waiting only for its own upstream, under one Semaphore.

    The node is found by its `use` in `nodes`, a frozen table built at the composition root. A node not due at the
    run's cadence is `idle`; a `green`-guarded node over a red upstream is `skip`; a `settled` one runs anyway (a
    verdict reads red gates). An exception is an `error`, never a crashed run. A (node, subject) whose inputs did not
    move since the ledger last recorded it is not paid for twice."""

    __slots__ = ("_concurrency", "_nodes", "_notify")

    def __init__(
        self,
        nodes: Mapping[str, PlaneNodePort],
        concurrency: int,
        notify: Callable[[NodeRun], None] | None = None,
    ) -> None:
        self._nodes = nodes
        self._concurrency = concurrency
        self._notify = notify or (lambda _: None)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_subjects(state: PlaneState, spec: NodeSpec) -> tuple[str, ...]:
        return ("",) if spec.card.scope is Scope.CORPUS else state.manifest.subjects

    @staticmethod
    def _run_keys(state: PlaneState, spec: NodeSpec, subject: str) -> tuple[tuple[str, str], ...]:
        """The (node, subject) pairs this one waits for: its own subject's, a corpus node's, or — for a corpus node
        after a subject node — every subject's."""
        graph = state.manifest.graph
        return tuple(
            key
            for dep in spec.depends
            for key in (
                ((dep, subject if graph[dep].card.scope is Scope.SUBJECT else ""),)
                if subject or graph[dep].card.scope is Scope.CORPUS
                else tuple((dep, each) for each in state.manifest.subjects)
            )
        )

    @staticmethod
    def _run_hash(state: PlaneState, spec: NodeSpec, subject: str, upstream: tuple[NodeRun, ...]) -> str:
        manifest = state.manifest
        payload = (spec, subject, manifest.base_sha, manifest.tree, sorted(run.output_hash for run in upstream))
        return hashlib.sha256(ENCODER.encode(payload)).hexdigest()

    @staticmethod
    def _run_gate(state: PlaneState, spec: NodeSpec, upstream: tuple[NodeRun, ...]) -> Outcome | None:
        """The outcome a node gets without running, or None when it must run."""
        red = next((run for run in upstream if not run.status.green), None)
        match (spec.due(state.manifest.cadence), spec.selected(state.manifest.only), spec.card.guard, red):
            case (False, _, _, _):
                return Outcome(status=Status.IDLE, reason=f"not due at cadence {state.manifest.cadence}")
            case (True, False, _, _):
                return Outcome(status=Status.IDLE, reason="not selected by --only")
            case (True, True, Guard.GREEN, NodeRun() as blocked):
                return Outcome(status=Status.SKIP, reason=f"upstream {blocked.node} is {blocked.status}")
            case _:
                return None

    @staticmethod
    def _run_kept(state: PlaneState, spec: NodeSpec, subject: str, digest: str) -> NodeRun | None:
        match state.ledger.latest(spec.id, subject):
            case NodeRun(input_hash=seen, status=status) as kept if seen == digest and status is not Status.ERROR:
                return kept
            case _:
                return None

    async def _run_call(self, state: PlaneState, spec: NodeSpec, subject: str, gate: asyncio.Semaphore) -> Outcome:
        async with gate:
            try:
                return await self._nodes[spec.use].run(PlaneContext(state=state, spec=spec, subject=subject))
            except Exception as exc:  # noqa: BLE001 — a node's failure is evidence, not a crash
                return Outcome(status=Status.ERROR, reason=f"{type(exc).__name__}: {exc}"[:REASON])

    async def _run_fresh(
        self,
        state: PlaneState,
        spec: NodeSpec,
        subject: str,
        gate: asyncio.Semaphore,
        upstream: tuple[NodeRun, ...],
    ) -> NodeRun:
        digest = self._run_hash(state, spec, subject, upstream)
        started = dt.datetime.now(dt.UTC)
        outcome = self._run_gate(state, spec, upstream) or await self._run_call(state, spec, subject, gate)
        run = NodeRun(
            run_id=state.manifest.run_id,
            node=spec.id,
            subject=subject,
            status=outcome.status,
            started=started,
            ended=dt.datetime.now(dt.UTC),
            input_hash=digest,
            output_hash=hashlib.sha256(ENCODER.encode(outcome)).hexdigest(),
            metrics=outcome.metrics,
            reason=outcome.reason,
            tokens=outcome.tokens,
            cached=outcome.cached,
            runner=outcome.runner,
            artifacts=outcome.artifacts,
        )
        await state.ledger.append(run)
        self._notify(run)
        return run

    async def _run_ready(
        self,
        state: PlaneState,
        spec: NodeSpec,
        subject: str,
        gate: asyncio.Semaphore,
        events: dict[tuple[str, str], asyncio.Event],
    ) -> NodeRun:
        """Wait for this pair's own upstream, run it, then release its dependents — even on error."""
        try:
            keys = self._run_keys(state, spec, subject)
            await asyncio.gather(*(events[key].wait() for key in keys))
            upstream = tuple(run for dep, each in keys if (run := state.ledger.latest(dep, each)))
            digest = self._run_hash(state, spec, subject, upstream)
            return self._run_kept(state, spec, subject, digest) or await self._run_fresh(
                state, spec, subject, gate, upstream
            )
        finally:
            events[spec.id, subject].set()

    ############################################################

    ##### PUBLIC #####

    async def run(self, state: PlaneState) -> tuple[NodeRun, ...]:
        """Every (node, subject) as one task that starts when its own upstream ended, under one bound."""
        gate = asyncio.Semaphore(self._concurrency)
        pairs = [(spec, subject) for spec in state.manifest.graph for subject in self._run_subjects(state, spec)]
        events = {(spec.id, subject): asyncio.Event() for spec, subject in pairs}
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(self._run_ready(state, spec, subject, gate, events)) for spec, subject in pairs]
        return tuple(task.result() for task in tasks)
