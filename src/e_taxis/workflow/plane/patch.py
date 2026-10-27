"""plane.patch: for a promotable verdict (`adopt`, `propose`), the exact diff that turns the base into the sandbox
under the subject's place, new files included — `patches/<target>/<subject>.patch`, all `enhance promote` (and a
candidate evaluation) ever applies."""

import hashlib
from typing import TYPE_CHECKING, ClassVar

import anyio

from e_taxis.workflow.models.metrics import DecisionMetrics, PatchMetrics
from e_taxis.workflow.models.plane import Guard, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status
from e_taxis.workflow.models.verdict import Decision

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import PlaneContext, SandboxPort

##### DEFAULTS #####
NEW: str = "+++ b/"


##### TYPES #####
class PlanePatch:
    """Satisfies PlaneNodePort."""

    __slots__ = ("_sandbox",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.EMIT, summary="the subject's patch against the base commit", guard=Guard.SETTLED
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    async def _run_cut(self, context: PlaneContext) -> Outcome:
        manifest, paths = context.state.manifest, context.state.paths
        diff = await self._sandbox.diff(paths.sandbox, manifest.base_sha, manifest.place(context.subject))
        target = paths.patches / manifest.target.value / f"{context.subject}.patch"
        await anyio.Path(target.parent).mkdir(parents=True, exist_ok=True)
        await anyio.Path(target).write_text(diff)
        lines = diff.splitlines()
        return Outcome(
            status=Status.OK,
            artifacts=(str(target),),
            metrics=PatchMetrics(
                path=str(target),
                files=tuple(line.removeprefix(NEW) for line in lines if line.startswith(NEW)),
                added=sum(line.startswith("+") and not line.startswith("+++") for line in lines),
                removed=sum(line.startswith("-") and not line.startswith("---") for line in lines),
                sha256=hashlib.sha256(diff.encode()).hexdigest(),
            ),
        )

    async def run(self, context: PlaneContext) -> Outcome:
        match context.upstream(context.param("decide", "decide")):
            case NodeRun(metrics=DecisionMetrics(decision=decision)) if Decision(decision).promotable:
                return await self._run_cut(context)
            case _:
                return Outcome(status=Status.IDLE, reason="verdict not promotable")
