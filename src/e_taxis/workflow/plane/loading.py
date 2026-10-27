"""plane.loading: what the real harness loads of the corpus — the v2 trial (`TrialService`): the tree under measure
rendered into a sandboxed home, the harness raised there under the Landlock fence (`LandrunFence`, canary first) with
a fake model (`HttpCapture`), and every entity it rendered looked for in what reached that model.

v1 asked the live coder (`opencode debug config|skill`) against the working tree; the trial is its v2 counterpart
and never touches the live tree. A machine reading: nothing depends on it, nightly and weekly only."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.models.metrics import LoadingMetrics
from e_taxis.workflow.models.plane import Cadence, Guard, NodeCard, Role, Scope
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.transpile.models.ports import CapturePort
    from e_taxis.workflow.models.ports import PlaneContext, TrialPort


##### TYPES #####
class PlaneLoading:
    """Satisfies PlaneNodePort over the trial and its fake model."""

    __slots__ = ("_capture", "_trial")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.MEASURE,
        summary="what the real harness, fenced on the render, loads of what the core declares",
        scope=Scope.CORPUS,
        guard=Guard.SETTLED,
        cadence=(Cadence.NIGHTLY, Cadence.WEEKLY),
    )

    def __init__(self, trial: TrialPort, capture: CapturePort) -> None:
        self._trial = trial
        self._capture = capture

    async def run(self, context: PlaneContext) -> Outcome:
        manifest = context.state.manifest
        report = await self._trial.run(GitNous(Path(manifest.tree), None), manifest.backend, self._capture)
        invisible = tuple(f"{sight.entity}:{name}" for sight in report.sights for name in sight.missing)
        return Outcome(
            status=Status.OK if report.held else Status.FAIL,
            metrics=LoadingMetrics(
                backend=manifest.backend, declared=sum(sight.expected for sight in report.sights), invisible=invisible
            ),
            reason="" if report.held else f"{len(invisible)} invisible, {report.captured} probe(s) reached the model",
        )
