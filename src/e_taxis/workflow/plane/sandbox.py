"""plane.sandbox: the enhancement's clone of the checkout at its base — its own `.git`, never a worktree — under the
run's folder. Every write of the run lands here; the checkout is untouched until `enhance promote`."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.workflow.models.metrics import SandboxMetrics
from e_taxis.workflow.models.plane import NodeCard, Role, Scope
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import PlaneContext, SandboxPort


##### TYPES #####
class PlaneSandbox:
    """Satisfies PlaneNodePort."""

    __slots__ = ("_sandbox",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="clone at the base commit: the only core/ a run edits", scope=Scope.CORPUS
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    async def run(self, context: PlaneContext) -> Outcome:
        manifest, paths = context.state.manifest, context.state.paths
        path = await self._sandbox.open(Path(manifest.nous), paths.sandbox, manifest.base_sha)
        return Outcome(status=Status.OK, metrics=SandboxMetrics(path=str(path), base_sha=manifest.base_sha))
