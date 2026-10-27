"""plane.decide: five endings, one pure function over the subject's ledger rows — the same rows, the same verdict.

It reads the candidate, every gate `params.gates` names, every proposal and the grade, and concludes the heaviest
finding: `settled` the candidate changed nothing · `reject` a gate is red · `hold` a gate broke, was skipped or never
ran · `propose` green but a gate idled, or the grade is above the target's ceiling · `adopt` green, and the grade
within the ceiling (`TAXIS_EVAL_PROMOTE`). Needs no proposer acts on (`routing`, `coverage`, `broken`) are carried as
reasons, never weight.

A green gate whose metrics carry a reading is read, not just counted: `effect` proposes when underpowered (fewer than
six tasks or three seeds) or inconclusive, rejects when an interval lies wholly below zero, adopts when the soft one
lies wholly above; `activation` rejects a candidate whose routing interval lies wholly below the base's."""

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final

from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.models.metrics import (
    ActivationMetrics,
    BriefMetrics,
    CandidateMetrics,
    DecisionMetrics,
    EffectMetrics,
    GradeMetrics,
)
from e_taxis.workflow.models.plane import Guard, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status
from e_taxis.workflow.models.verdict import Decision

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.ports import PlaneContext

##### DEFAULTS #####
### heaviest first: the verdict is the heaviest finding.
WEIGHT: Final[tuple[Decision, ...]] = (Decision.REJECT, Decision.HOLD, Decision.PROPOSE, Decision.ADOPT)
### how a gate's status reads.
BY_STATUS: Final[Mapping[Status, Decision]] = MappingProxyType(
    {
        Status.OK: Decision.ADOPT,
        Status.FAIL: Decision.REJECT,
        Status.ERROR: Decision.HOLD,
        Status.SKIP: Decision.HOLD,
        Status.IDLE: Decision.PROPOSE,
    }
)
### needs no proposer acts on: the description has its own owner, the case ledgers are written by hand.
UNADDRESSED: Final[frozenset[str]] = frozenset({"routing", "coverage", "broken"})
NONE: str = "none"
MATRIX: str = "core/versioning/matrix.yaml"
### below this an effect A/B is underpowered: its interval is no verdict.
MIN_TASKS: int = 6
MIN_SEEDS: int = 3

type Finding = tuple[Decision, str]


##### UTILITIES #####
def read_effect(_context: PlaneContext, effect: EffectMetrics) -> Finding:
    summary = (
        f"effect soft {effect.delta.soft:+.3f} [{effect.soft.low:+.3f}, {effect.soft.high:+.3f}] "
        f"hard {effect.delta.hard:+.3f} [{effect.hard.low:+.3f}, {effect.hard.high:+.3f}] "
        f"n={effect.tasks}x{effect.seeds}"
    )
    match (
        effect.tasks < MIN_TASKS or effect.seeds < MIN_SEEDS,
        effect.soft.high < 0 or effect.hard.high < 0,
        effect.soft.low > 0,
    ):
        case (True, _, _):
            return (Decision.PROPOSE, f"underpowered · {summary}")
        case (_, True, _):
            return (Decision.REJECT, f"worse · {summary}")
        case (_, _, True):
            return (Decision.ADOPT, f"better · {summary}")
        case _:
            return (Decision.PROPOSE, f"inconclusive · {summary}")


def read_activation(context: PlaneContext, candidate: ActivationMetrics) -> Finding:
    summary = f"routing {candidate.rate:.1f}% [{candidate.interval.low:.0f}-{candidate.interval.high:.0f}]"
    match context.upstream(context.param("activation_base", "activation_base")):
        case NodeRun(metrics=ActivationMetrics(interval=base)) if candidate.interval.high < base.low:
            return (Decision.REJECT, f"{summary} below base [{base.low:.0f}-{base.high:.0f}]")
        case _:
            return (Decision.ADOPT, summary)


### metrics that carry a reading beyond their status; any other green gate is simply green.
READERS: Final[Mapping[type, Callable[..., Finding]]] = MappingProxyType(
    {EffectMetrics: read_effect, ActivationMetrics: read_activation}
)


##### TYPES #####
class PlaneDecide:
    """Satisfies PlaneNodePort; `ceilings` is target → the heaviest grade adopted without a human, weighed on the
    checkout's versioning matrix."""

    __slots__ = ("_ceilings",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.DECIDE, summary="pure verdict over the subject's ledger rows", guard=Guard.SETTLED
    )

    def __init__(self, ceilings: Mapping[str, str]) -> None:
        self._ceilings = ceilings

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_gate(context: PlaneContext, gate: str) -> Finding:
        match context.upstream(gate):
            case None:
                return (Decision.HOLD, f"{gate}: never ran")
            case NodeRun(status=Status.OK, metrics=metrics) if (reader := READERS.get(type(metrics))) is not None:
                return reader(context, metrics)
            case NodeRun(status=Status.OK):
                return (Decision.ADOPT, f"{gate} green")
            case run:
                return (BY_STATUS[run.status], f"{gate}: {run.status} {run.reason}".strip())

    async def _run_ceiling(self, context: PlaneContext, grade: GradeMetrics | None) -> Finding:
        manifest = context.state.manifest
        ceiling = self._ceilings.get(manifest.target.value, NONE)
        name = grade.grade if grade else "?"
        match (grade, ceiling):
            case (GradeMetrics(), str()) if ceiling != NONE:
                matrix = await VersionMatrix.load(Path(manifest.nous) / MATRIX)
                within = matrix[name].level <= matrix[ceiling].level
            case _:
                within = False
        return (
            (Decision.ADOPT, f"grade {name} ≤ ceiling {ceiling}")
            if within
            else (Decision.PROPOSE, f"grade {name} above ceiling {ceiling}")
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        match context.upstream(context.param("candidate", "candidate")):
            case NodeRun(metrics=CandidateMetrics(changed=())):
                verdict = DecisionMetrics(decision=Decision.SETTLED, reasons=("no proposer changed this subject",))
                return Outcome(status=Status.OK, metrics=verdict)
            case _:
                pass
        match context.upstream(context.param("grade", "grade")):
            case NodeRun(metrics=GradeMetrics() as grade):
                pass
            case _:
                grade = None
        match context.upstream("intake"):
            case NodeRun(metrics=BriefMetrics(needs=needs)):
                pass
            case _:
                needs = ()
        findings = [
            *(self._run_gate(context, gate) for gate in context.param("gates").split(",") if gate),
            *(
                (Decision.ADOPT, f"unaddressed {need.kind} need: {need.detail}")
                for need in needs
                if need.kind in UNADDRESSED
            ),
            await self._run_ceiling(context, grade),
        ]
        decision = next(
            level for level in WEIGHT if level in {found for found, _ in findings} or level is Decision.ADOPT
        )
        reasons = tuple(reason for level, reason in findings if level in {decision, Decision.ADOPT})
        return Outcome(
            status=Status.OK,
            metrics=DecisionMetrics(
                decision=decision, reasons=reasons, grade=grade.grade if grade else "", bump=grade.bump if grade else ""
            ),
        )
