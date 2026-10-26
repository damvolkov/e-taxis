"""engine.executor: the graph manager — graphlib checks the order, one TaskGroup runs, the ledger remembers.

Every step becomes one task of a single TaskGroup that waits only for its own upstream: a step starts the moment
its dependencies ended, never at a wave boundary, so independent branches overlap. One Semaphore bounds the run.

A step never takes the run down. An exception becomes an `error` outcome, a red upstream a `skip` — all recorded.
The executor is the only writer of the ledger, and `notify` hears each record as it lands. A step whose inputs did
not move since the ledger last recorded it (same input hash, not an error) is not paid for twice.

graphlib, not rustworkx: the order of a dozen steps is no hot path, and graphlib is already this repo's DAG tool."""

import asyncio
import datetime as dt
import graphlib
import hashlib
from typing import TYPE_CHECKING, Final

import msgspec

from e_taxis.workflow.models.error import WorkflowError
from e_taxis.workflow.models.ports import NodeContext
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.graph import StepSpec
    from e_taxis.workflow.models.ports import NodePort, RunState

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
