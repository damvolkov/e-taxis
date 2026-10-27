"""plane.effect: does the skill make an answer better — a paired A/B on held-out tasks, the only evidence a skill edit
is adopted on.

Each task of the skill's set in `TAXIS_EVAL_EFFECT_SPLIT` (`test`: never a split a proposer learned or gated on) is
answered `TAXIS_EVAL_EFFECT_SEEDS` times under two contexts, by a bare completion on the house tier
`TAXIS_EVAL_TIER` — no harness, index or persona leaks in; the judge is deterministic, the interval a seeded
bootstrap over whole tasks. The context of a skill is the whole skill: its router, then every reference by name.

| `params.mode` | plane | A | B | answers |
|---|---|---|---|---|
| `value` | evaluator | no skill | the skill as it stands | does the skill help, and which tasks still fail under it |
| `delta` | enhancer | the skill as it stands | the candidate | did the enhancement help |

Paid in tokens (tasks x seeds x 2 completions), so weekly; idle with no tasks in the split, or on a candidate that
did not move. Every answer's score is kept beside the node (`outcomes.json`)."""

import asyncio
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING, ClassVar

import anyio
import msgspec

from e_taxis.workflow.engine.judge import RuleJudge
from e_taxis.workflow.engine.stats import interval_bootstrap
from e_taxis.workflow.models.metrics import CandidateMetrics, EffectMetrics, Interval, Score
from e_taxis.workflow.models.plane import Cadence, Nature, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Sequence

    from e_taxis.workflow.models.case import TaskCase
    from e_taxis.workflow.models.endpoint import Endpoint
    from e_taxis.workflow.models.ports import EvalsPort, PlaneContext, ProviderPort, RunnerPort

##### DEFAULTS #####
VALUE: str = "value"
DELTA: str = "delta"
BOOT: int = 10_000
ALPHA: float = 0.05
RUNNER: str = "anthropic"
OUTCOMES: str = "outcomes.json"

type Grid = list[list[tuple[Score, int]]]


##### TYPES #####
class PlaneEffect:
    """Satisfies PlaneNodePort over the checkout's task sets, the tier's endpoint and a bare-completion runner; one
    gate bounds every completion of the run."""

    __slots__ = ("_evals", "_gate", "_provider", "_runner", "_seeds", "_split", "_tier")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.MEASURE,
        summary="paired A/B on held-out tasks: value (none vs skill) or delta (base vs candidate)",
        nature=Nature.HEURISTIC,
        cadence=(Cadence.WEEKLY,),
    )

    def __init__(
        self,
        evals: EvalsPort,
        provider: ProviderPort,
        runner: RunnerPort,
        *,
        tier: str,
        seeds: int,
        split: str,
        concurrency: int,
    ) -> None:
        self._evals = evals
        self._provider = provider
        self._runner = runner
        self._tier = tier
        self._seeds = seeds
        self._split = split
        self._gate = asyncio.Semaphore(concurrency)

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _run_context(flat: Path, subject: str) -> str:
        """The whole skill as context: the router, then every reference, in name order."""
        folder = anyio.Path(flat / "skills" / subject)
        references = sorted([path async for path in (folder / "references").glob("*.md")])
        files = [path for path in (folder / "SKILL.md", *references) if await path.is_file()]
        return "\n\n".join([f"<!-- {path.relative_to(folder)} -->\n{await path.read_text()}" for path in files])

    async def _run_answer(self, endpoint: Endpoint, system: str, task: TaskCase) -> tuple[Score, int]:
        async with self._gate:
            reply = await self._runner.complete(endpoint, task.prompt, system=system)
        return RuleJudge.score(task.checks, reply.text), reply.tokens

    async def _run_grid(self, endpoint: Endpoint, system: str, tasks: Sequence[TaskCase]) -> Grid:
        """Every task answered `seeds` times under one context."""
        async with asyncio.TaskGroup() as group:
            cells = [
                [group.create_task(self._run_answer(endpoint, system, task)) for _ in range(self._seeds)]
                for task in tasks
            ]
        return [[cell.result() for cell in row] for row in cells]

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        state, mode = context.state, context.param("mode", DELTA)
        nous = Path(state.manifest.nous)
        found, _ = await self._evals.tasks(nous, context.subject)
        tasks = [task for task in (found.tasks if found else ()) if task.split.value == self._split]
        match (mode, context.upstream("candidate"), tasks):
            case ("delta", NodeRun(metrics=CandidateMetrics(changed=())), _):
                return Outcome(status=Status.IDLE, reason="candidate unchanged")
            case (_, _, []):
                return Outcome(status=Status.IDLE, reason=f"no {self._split} tasks")
            case _:
                pass
        endpoint = await self._provider.endpoint(nous, self._tier)
        ### value: no skill against the skill as it stands; delta: the skill as it stands against the candidate.
        before = "" if mode == VALUE else await self._run_context(state.paths.base, context.subject)
        after_flat = state.paths.base if mode == VALUE else state.paths.candidate(context.subject)
        after = await self._run_context(after_flat, context.subject)
        async with asyncio.TaskGroup() as group:
            base_task = group.create_task(self._run_grid(endpoint, before, tasks))
            candidate_task = group.create_task(self._run_grid(endpoint, after, tasks))
        base, candidate = base_task.result(), candidate_task.result()
        hard = [[[score.hard for score, _ in row] for row in grid] for grid in (base, candidate)]
        soft = [[[score.soft for score, _ in row] for row in grid] for grid in (base, candidate)]
        dh, hl, hh = interval_bootstrap(hard[0], hard[1], BOOT, ALPHA)
        ds, sl, sh = interval_bootstrap(soft[0], soft[1], BOOT, ALPHA)
        await anyio.Path(context.workdir).mkdir(parents=True, exist_ok=True)
        raw = context.workdir / OUTCOMES
        await anyio.Path(raw).write_bytes(
            msgspec.json.encode(
                {
                    "base": [[score for score, _ in row] for row in base],
                    "candidate": [[score for score, _ in row] for row in candidate],
                    "tasks": [task.id for task in tasks],
                }
            )
        )
        return Outcome(
            status=Status.OK,
            runner=RUNNER,
            artifacts=(str(raw),),
            tokens=sum(spent for grid in (base, candidate) for row in grid for _, spent in row),
            metrics=EffectMetrics(
                split=self._split,
                tasks=len(tasks),
                seeds=self._seeds,
                base=Score(fmean(map(fmean, hard[0])), fmean(map(fmean, soft[0]))),
                candidate=Score(fmean(map(fmean, hard[1])), fmean(map(fmean, soft[1]))),
                delta=Score(dh, ds),
                hard=Interval(hl, hh),
                soft=Interval(sl, sh),
                per_task={task.id: (fmean(hard[0][i]), fmean(hard[1][i])) for i, task in enumerate(tasks)},
                mode=mode,
            ),
        )
