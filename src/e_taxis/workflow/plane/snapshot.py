"""plane.snapshot: the world a run started from — its base, the checkout's dirty paths, every tool a verdict leans on.

Zero tokens, never red: a snapshot records, it does not judge. A tool that does not answer reads `absent`."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from e_taxis.workflow.models.error import CommandError
from e_taxis.workflow.models.metrics import SnapshotMetrics
from e_taxis.workflow.models.plane import Guard, NodeCard, Role, Scope
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import CommandPort, PlaneContext, SandboxPort

##### DEFAULTS #####
TOOLS: Final[tuple[str, ...]] = ("claude", "opencode", "uv", "git")
ABSENT: str = "absent"
LIMIT: float = 30.0
SCOPE: tuple[str, ...] = ("core", "specs")


##### TYPES #####
class PlaneSnapshot:
    """Satisfies PlaneNodePort."""

    __slots__ = ("_command", "_sandbox")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="base commit, dirty paths, tool versions", scope=Scope.CORPUS, guard=Guard.SETTLED
    )

    def __init__(self, command: CommandPort, sandbox: SandboxPort) -> None:
        self._command = command
        self._sandbox = sandbox

    ##### PRIVATE METHODS #####

    async def _run_version(self, tool: str) -> str:
        try:
            said = await self._command.run(tool, "--version", limit=LIMIT)
        except CommandError:
            return ABSENT
        return next(iter(said.strip().splitlines()), ABSENT)

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        manifest = context.state.manifest
        dirty = await self._sandbox.dirty(Path(manifest.nous), *SCOPE)
        tools = {tool: await self._run_version(tool) for tool in TOOLS}
        return Outcome(status=Status.OK, metrics=SnapshotMetrics(base_sha=manifest.base_sha, dirty=dirty, tools=tools))
