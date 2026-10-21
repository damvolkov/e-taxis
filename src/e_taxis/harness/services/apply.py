"""services.apply: the plan, carried out — install and update steps in requires order, through one primitive each.

Before anything is written, apply refuses whole: unknown parts, and blocked parts whose gate the run does
not open (`--accept-licence ID`, `--confirm ID`, every secret set in the environment). Then each step runs
in order: skips and deferrals are reported, the rest go through the primitive their recipe names. The first
failure stops the run (later steps are `not-run`). Every change a primitive reports — or carried in the
error it failed with — goes to the recorder at once, so the journal can undo even a failed run. Each applied
part's `verify` runs last."""

import asyncio
from typing import TYPE_CHECKING

from e_taxis.harness.models.apply import ApplyReport, ApplyStatus, ApplyStep
from e_taxis.harness.models.error import ApplyError, PrimitiveError
from e_taxis.harness.models.plan import Plan, PlanAction, PlanStep
from e_taxis.harness.models.primitive import NotSupportedYet, PrimitiveContext
from e_taxis.harness.models.verify import VerifyResult

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from e_taxis.harness.models.apply import ApplyOptions
    from e_taxis.harness.models.catalog import CatalogEntry, Primitive, Target
    from e_taxis.harness.models.ports import PrimitivePort, ProbePort, RecorderPort, SourcePort
    from e_taxis.harness.services.plan import PlanService
    from e_taxis.harness.services.resolver import ResolverService


##### TYPES #####
class ApplyService:
    """Resolver and planner for what to do, the primitive table to do it, the recorder to make it undoable.

    `home` and `claude` anchor every `~` a recipe names; `environ` is where gate secrets are looked up."""

    __slots__ = ("_claude", "_environ", "_home", "_planner", "_primitives", "_probe", "_recorder", "_resolver")

    def __init__(
        self,
        resolver: ResolverService,
        planner: PlanService,
        probe: ProbePort,
        primitives: Mapping[Primitive, PrimitivePort],
        recorder: RecorderPort,
        *,
        home: Path,
        claude: Path,
        environ: Mapping[str, str],
    ) -> None:
        self._resolver = resolver
        self._planner = planner
        self._probe = probe
        self._primitives = primitives
        self._recorder = recorder
        self._home = home
        self._claude = claude
        self._environ = environ

    ##### PRIVATE METHODS #####

    async def _common_plan(
        self, source: SourcePort, target: Target, only: frozenset[str]
    ) -> tuple[Plan, dict[str, CatalogEntry]]:
        resolution = await self._resolver.resolve(source, target)
        plan = await self._planner.decide(resolution, target)
        match sorted(only - {step.id for step in plan.steps}):
            case []:
                pass
            case stray:
                msg = f"--only names {', '.join(stray)}, not in the plan for {target}"
                raise ApplyError(msg)
        steps = tuple(step for step in plan.steps if not only or step.id in only)
        return (Plan(target=target, steps=steps), {item.entry.id: item.entry for item in resolution.resolved})

    def _run_closed(self, entry: CatalogEntry, options: ApplyOptions) -> tuple[str, ...]:
        """What the run still lacks to open the entry's gate: flags to pass, secrets to set."""
        gate = entry.gate
        return (
            *((f"--accept-licence {entry.id}",) if gate.licence and entry.id not in options.licences else ()),
            *((f"--confirm {entry.id}",) if gate.confirm and entry.id not in options.confirms else ()),
            *(f"${name} set" for name in gate.secrets if not self._environ.get(name)),
        )

    def _run_refusals(self, plan: Plan, entries: dict[str, CatalogEntry], options: ApplyOptions) -> None:
        refused = [
            *(f"{step.id} has no catalog entry" for step in plan.steps if step.action is PlanAction.UNKNOWN),
            *(
                f"{step.id} needs {', '.join(lacking)}"
                for step in plan.steps
                if step.action is PlanAction.BLOCKED and (lacking := self._run_closed(entries[step.id], options))
            ),
        ]
        match refused:
            case []:
                pass
            case _:
                msg = f"apply refused, nothing written — {'; '.join(refused)}"
                raise ApplyError(msg)

    async def _run_write(self, step: PlanStep, entry: CatalogEntry, target: Target) -> ApplyStep:
        ### a blocked step that reached here had its gate opened: it does what it held back.
        update = (step.held or step.action) is PlanAction.UPDATE
        ctx = PrimitiveContext(target=target, home=self._home, claude=self._claude, update=update)
        match entry.recipe(target):
            case None:
                return ApplyStep(id=entry.id, status=ApplyStatus.FAILED, detail=f"no recipe for {target}")
            case recipe:
                try:
                    result = await self._primitives[recipe.primitive].install(entry, recipe, ctx)
                except PrimitiveError as exc:
                    self._recorder.record(*exc.effects)
                    return ApplyStep(id=entry.id, status=ApplyStatus.FAILED, detail=exc.message)
                except OSError as exc:
                    ### the disk refused (permissions, a directory where a file goes): a failed step, not a crash.
                    return ApplyStep(id=entry.id, status=ApplyStatus.FAILED, detail=str(exc))
        match result:
            case NotSupportedYet(detail=detail):
                return ApplyStep(id=entry.id, status=ApplyStatus.DEFERRED, detail=detail)
            case done:
                self._recorder.record(*done.effects)
                return ApplyStep(id=entry.id, status=ApplyStatus.APPLIED, detail=done.detail)

    async def _run_step(self, step: PlanStep, entries: dict[str, CatalogEntry], target: Target) -> ApplyStep:
        match step.action:
            case PlanAction.SKIP:
                return ApplyStep(id=step.id, status=ApplyStatus.SKIPPED, detail=step.reason)
            case PlanAction.DEFERRED:
                return ApplyStep(id=step.id, status=ApplyStatus.DEFERRED, detail=step.reason)
            case _:
                return await self._run_write(step, entries[step.id], target)

    async def _run_verify(self, steps: list[ApplyStep], entries: dict[str, CatalogEntry]) -> tuple[VerifyResult, ...]:
        applied = [step.id for step in steps if step.status is ApplyStatus.APPLIED]
        probes = await asyncio.gather(*(self._probe.run(entries[part].verify) for part in applied))
        return tuple(
            VerifyResult(id=part, passed=probe.present, detail=probe.detail)
            for part, probe in zip(applied, probes, strict=True)
        )

    ############################################################

    ##### PUBLIC #####

    async def plan(self, source: SourcePort, target: Target, only: frozenset[str]) -> Plan:
        """The plan apply would carry out, narrowed to `only` when given. Writes nothing."""
        plan, _ = await self._common_plan(source, target, only)
        return plan

    async def run(self, source: SourcePort, target: Target, options: ApplyOptions) -> ApplyReport:
        plan, entries = await self._common_plan(source, target, options.only)
        self._run_refusals(plan, entries, options)
        steps: list[ApplyStep] = []
        ### sequential on purpose: each step may need what the one before it installed.
        for step in plan.steps:
            halted = bool(steps) and steps[-1].status in {ApplyStatus.FAILED, ApplyStatus.NOT_RUN}
            steps.append(
                ApplyStep(id=step.id, status=ApplyStatus.NOT_RUN, detail="an earlier step failed")
                if halted
                else await self._run_step(step, entries, target)
            )
        return ApplyReport(target=target, steps=tuple(steps), verify=await self._run_verify(steps, entries))
