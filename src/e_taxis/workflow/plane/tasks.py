"""plane.tasks: the skill's effect ledger holds before any proposer or A/B is paid for — unique ids, every split
populated, judges that are outcomes, regexes that compile. A skill without a task set is `idle`: its effect is not
measured (a coverage need)."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.workflow.models.case import TaskSet
from e_taxis.workflow.models.metrics import LedgerMetrics
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import EvalsPort, PlaneContext

##### DEFAULTS #####
NONE: str = "no task set"


##### TYPES #####
class PlaneTasks:
    """Satisfies PlaneNodePort over the checkout's ledgers."""

    __slots__ = ("_evals",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="effect task set parses, splits populated, judges are outcomes"
    )

    def __init__(self, evals: EvalsPort) -> None:
        self._evals = evals

    async def run(self, context: PlaneContext) -> Outcome:
        found, where = await self._evals.tasks(Path(context.state.manifest.nous), context.subject)
        match found:
            case None | TaskSet(tasks=()):
                return Outcome(status=Status.IDLE, reason=NONE)
            case tasks:
                problems = tasks.problems
                return Outcome(
                    status=Status.FAIL if problems else Status.OK,
                    metrics=LedgerMetrics(
                        kind="tasks", cases=len(tasks.tasks), problems=problems, where=where, splits=tasks.splits
                    ),
                )
