"""plane.queries: the skill's routing ledger holds before any probe is paid for — every cited skill exists, every
cited reference exists beside its skill. A skill without a query set is `idle`: its routing is simply not measured
(and `needs` reads that as a coverage need)."""

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, ClassVar

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.models.metrics import LedgerMetrics
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import EvalsPort, PlaneContext

##### DEFAULTS #####
NONE: str = "no query set"
SKILL: str = "skill"


##### TYPES #####
class PlaneQueries:
    """Satisfies PlaneNodePort over the checkout's ledgers."""

    __slots__ = ("_evals",)

    card: ClassVar[NodeCard] = NodeCard(role=Role.GATE, summary="routing query set parses and cites only what exists")

    def __init__(self, evals: EvalsPort) -> None:
        self._evals = evals

    async def run(self, context: PlaneContext) -> Outcome:
        manifest = context.state.manifest
        found, where = await self._evals.queries(Path(manifest.nous), context.subject)
        match found:
            case None:
                return Outcome(status=Status.IDLE, reason=NONE)
            case queries:
                pass
        skills = (await GitNous(Path(manifest.tree), None).load()).entities.get(SKILL, {})
        references = frozenset(
            f"{ident}/{PurePosixPath(ref).name}"
            for ident, skill in skills.items()
            for ref in skill.get("references", ())
        )
        problems = queries.problems(frozenset(skills), references)
        return Outcome(
            status=Status.FAIL if problems else Status.OK,
            metrics=LedgerMetrics(kind="queries", cases=len(queries.cases), problems=problems, where=where),
        )
