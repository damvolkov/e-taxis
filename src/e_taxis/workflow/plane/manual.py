"""plane.manual: your working-tree edits of the subject as a proposal, on request (`--manual`) — overlaid onto the
sandbox byte for byte, deletions included, so a hand edit is measured base against candidate by the same gates as
a machine's. Without `--manual` it idles and the other proposers start from the committed state."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.workflow.models.metrics import ProposalMetrics
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import PlaneContext, SandboxPort

##### DEFAULTS #####
NOTHING: str = "no --manual: proposers start from the committed state"


##### TYPES #####
class PlaneManual:
    """Satisfies PlaneNodePort."""

    __slots__ = ("_sandbox",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.PROPOSE, summary="your working-tree edits of the subject, overlaid onto the sandbox (--manual)"
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    async def run(self, context: PlaneContext) -> Outcome:
        manifest, paths = context.state.manifest, context.state.paths
        match manifest.manual:
            case False:
                return Outcome(status=Status.IDLE, reason=NOTHING)
            case _:
                place, nous = manifest.place(context.subject), Path(manifest.nous)
        changed = await self._sandbox.changed(nous, manifest.base_sha, place)
        _ = changed and await self._sandbox.overlay(nous, paths.sandbox, place)
        return Outcome(status=Status.OK, metrics=ProposalMetrics(proposer="manual", files=changed))
