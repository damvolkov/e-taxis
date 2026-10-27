"""plane.activation: does each description win the routing decision it should — the probe over a render, never the
live tree.

The run's coder (`TAXIS_EVAL_BACKEND`) is pointed at `params.tree` — `base` (the render every subject is measured
on) or `candidate` (this subject's) — through a sandbox config home built around it, with every competing
description in the index. Each case of the skill's query set that asserts anything in `params.mode` (`activation`,
`navigation`, `preload`) runs `TAXIS_EVAL_PROBE_RUNS` clean sessions, at most `TAXIS_EVAL_PROBE_CONCURRENCY` in
flight across the whole run. A session the coder never answered is unmeasured — neither pass nor fail, so an API
error never reads as an under-trigger; a transient refusal (429, overloaded, a timeout) is retried with jittered
backoff, a quota is not. The reading: the pooled rate with its Wilson interval, recall over the positive cases and
precision over the negative ones, and the cases that did not hold every run. Unmeasured runs leave the node in
`skip`: a partial rate is no verdict, and no break either. Paid in tokens, so weekly; idle with no query set, with nothing to enhance,
or on a candidate that did not move (its routing is the base's)."""

import asyncio
import random
import re
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

import anyio

from e_taxis.workflow.engine.stats import interval_wilson
from e_taxis.workflow.models.case import ProbeMode, ProbeResult, QueryCase
from e_taxis.workflow.models.error import CommandError
from e_taxis.workflow.models.metrics import ActivationMetrics, CandidateMetrics, Interval
from e_taxis.workflow.models.plane import Cadence, Nature, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.workflow.models.ports import CoderPort, EvalsPort, PlaneContext

##### DEFAULTS #####
BASE: str = "base"
CANDIDATE: str = "candidate"
RETRIES: int = 2
BACKOFF: float = 5.0
PROMPT: int = 80
TRANSIENT: Final[re.Pattern[str]] = re.compile(r"\b429\b|rate.?limit|overloaded|timeout after", re.IGNORECASE)
TERMINAL: Final[re.Pattern[str]] = re.compile(r"session limit|quota|insufficient", re.IGNORECASE)

type Row = tuple[QueryCase, tuple[ProbeResult, ...]]


##### TYPES #####
class PlaneActivation:
    """Satisfies PlaneNodePort over the checkout's query sets and a coder per backend; one gate bounds every session
    of the run, whatever its subject."""

    __slots__ = ("_backoff", "_coders", "_evals", "_gate", "_limit", "_runs")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.MEASURE,
        summary="routing rate with Wilson interval, recall and precision, over a sandbox render",
        nature=Nature.HEURISTIC,
        cadence=(Cadence.WEEKLY,),
    )

    def __init__(
        self,
        evals: EvalsPort,
        coders: Mapping[str, CoderPort],
        *,
        runs: int,
        concurrency: int,
        limit: float,
        backoff: float = BACKOFF,
    ) -> None:
        self._evals = evals
        self._coders = coders
        self._runs = runs
        self._gate = asyncio.Semaphore(concurrency)
        self._limit = limit
        self._backoff = backoff

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_idle(context: PlaneContext, tree: str) -> str:
        """Why this run measures nothing, or empty."""
        match (context.upstream("intake"), context.upstream("queries"), tree, context.upstream(CANDIDATE)):
            case (NodeRun(status=Status.IDLE), _, _, _):
                return "nothing to enhance: routing not measured"
            case (_, NodeRun(status=Status.IDLE), _, _):
                return "no query set"
            case (_, _, "candidate", NodeRun(metrics=CandidateMetrics(changed=()))):
                return "candidate unchanged: routing is the base's"
            case _:
                return ""

    async def _run_attempt(
        self, coder: CoderPort, case: QueryCase, mode: ProbeMode, env: Mapping[str, str], attempt: int = 0
    ) -> ProbeResult:
        """One measured session, retried only where a retry can help; a refusal is a value, never an exception —
        raising would cancel the group and discard every session already paid for."""
        async with self._gate:
            try:
                return await coder.probe(case.prompt, mode, env=env, limit=self._limit)
            except CommandError as refusal:
                error = str(refusal)
        match attempt < RETRIES and bool(TRANSIENT.search(error)) and not TERMINAL.search(error):
            case True:
                ### the backoff waits outside the gate: a sleeping retry holds no slot.
                await asyncio.sleep(self._backoff * 2**attempt * random.uniform(0.7, 1.3))  # noqa: S311 — jitter
                return await self._run_attempt(coder, case, mode, env, attempt + 1)
            case _:
                return ProbeResult(error=error)

    @staticmethod
    def _run_metrics(tree: str, mode: ProbeMode, backend: str, rows: Sequence[Row]) -> ActivationMetrics:
        """The reading over every case: a case holds when every measured run held and at least one was measured."""
        tallies = [
            (
                case,
                sum(result.measured and case.holds(mode, result) for result in results),
                sum(result.measured for result in results),
            )
            for case, results in rows
        ]
        held = [(case, passes, measured, measured > 0 and passes == measured) for case, passes, measured in tallies]
        passes, measured = sum(row[1] for row in held), sum(row[2] for row in held)
        low, high = interval_wilson(passes, measured)
        positive = [ok for case, _, _, ok in held if case.positive(mode)]
        negative = [ok for case, _, _, ok in held if not case.positive(mode)]
        ### worst first; ties keep the set's order.
        failing = sorted(
            ((passes / measured if measured else 0.0, case.prompt) for case, passes, measured, ok in held if not ok),
            key=itemgetter(0),
        )
        return ActivationMetrics(
            tree=tree,
            mode=mode.value,
            backend=backend,
            passed=sum(ok for *_, ok in held),
            total=len(held),
            rate=passes / measured * 100 if measured else 0.0,
            interval=Interval(low * 100, high * 100),
            recall=(sum(positive), len(positive)),
            precision=(sum(negative), len(negative)),
            unmeasured=sum(len(results) for _, results in rows) - measured,
            failures=tuple(prompt[:PROMPT] for _, prompt in failing),
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        state, tree = context.state, context.param("tree", BASE)
        mode = ProbeMode(context.param("mode", ProbeMode.ACTIVATION.value))
        found, _ = await self._evals.queries(Path(state.manifest.nous), context.subject)
        match (self._run_idle(context, tree), found):
            case (str() as why, _) if why:
                return Outcome(status=Status.IDLE, reason=why)
            case (_, None):
                return Outcome(status=Status.IDLE, reason="no query set")
            case _:
                cases = [case for case in (found.cases if found else ()) if case.asserts(mode)]
        flat = state.paths.candidate(context.subject) if tree == CANDIDATE else state.paths.base
        coder = self._coders[state.manifest.backend]
        env = await coder.sandbox(flat, context.workdir / "home")
        try:
            async with asyncio.TaskGroup() as group:
                tasks = [
                    (case, [group.create_task(self._run_attempt(coder, case, mode, env)) for _ in range(self._runs)])
                    for case in cases
                ]
        finally:
            ### the borrowed credentials never outlive the probes: the run folder is a report, not a home.
            await anyio.Path(context.workdir / "home" / ".credentials.json").unlink(missing_ok=True)
        rows = [(case, tuple(task.result() for task in row)) for case, row in tasks]
        metrics = self._run_metrics(tree, mode, state.manifest.backend, rows)
        return Outcome(
            ### v1's `unmeasured`: no verdict (decide holds), yet no break — a rate limit never fails the run.
            status=Status.SKIP if metrics.unmeasured else Status.OK,
            reason=f"{metrics.unmeasured} sessions unmeasured" if metrics.unmeasured else "",
            metrics=metrics,
            tokens=sum(result.tokens for _, results in rows for result in results),
            runner=state.manifest.backend,
        )
