"""plane.signals: the drift a backend's spec carries — the v2 check's `signal` findings for that backend.

v1's `spec/check` fetched every upstream source and diffed it against a snapshot on this machine; the v2 transpiler's
law already states what a spec lags behind (its `upstream` versions, `verified against …`): those signals are the
reading here, offline and deterministic. `needs` reads each as a `drift` need — the speckeeper's only input."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.report import ReportKind
from e_taxis.workflow.models.metrics import SignalMetrics, SignalRow
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.transpile.services.check import CheckService
    from e_taxis.workflow.models.ports import PlaneContext


##### TYPES #####
class PlaneSignals:
    """Satisfies PlaneNodePort over the v2 check."""

    __slots__ = ("_checker",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.MEASURE, summary="the drift signals the v2 check states for a backend"
    )

    def __init__(self, checker: CheckService) -> None:
        self._checker = checker

    async def run(self, context: PlaneContext) -> Outcome:
        report = await self._checker.run(GitNous(Path(context.state.manifest.tree), None))
        rows = tuple(
            SignalRow(finding.where, finding.path, finding.detail)
            for finding in report.findings
            if finding.kind is ReportKind.SIGNAL and finding.backend == context.subject
        )
        return Outcome(status=Status.OK, metrics=SignalMetrics(backend=context.subject, signals=rows))
