"""plane.render: the base render — a v2 export (`RunService`) of the tree under measure, for the run's backend.

The evaluator renders the tree it was asked to measure (`tree=working`: the checkout as it stands, or the candidate
of an enhancer run); the enhancer renders its untouched sandbox (`tree=sandbox`), the base every candidate is
compared against, before any proposer moves a byte. A pure export into the run folder, never a live tree; the
spec's bindings are read from the harness's live tree under `home`, as `transpile run --out` reads them. A tree its
own law refuses does not render: the check's blocking findings are the node's failure."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import anyio

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.services.run import RunService
from e_taxis.workflow.models.metrics import RenderMetrics
from e_taxis.workflow.models.plane import NodeCard, Role, Scope
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.projection import Projection
    from e_taxis.workflow.models.ports import PlaneContext

##### DEFAULTS #####
WORKING: str = "working"
SANDBOX: str = "sandbox"


##### TYPES #####
class PlaneRender:
    """Satisfies PlaneNodePort over the v2 render and the HOME whose live trees hold the spec's bindings."""

    __slots__ = ("_home", "_runner")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="v2 render of the tree under measure, or of the untouched sandbox", scope=Scope.CORPUS
    )

    def __init__(self, runner: RunService, home: Path) -> None:
        self._runner = runner
        self._home = home

    ##### PRIVATE METHODS #####

    async def _common_bindings(self, tree: NousTree, backend: str) -> dict[str, str]:
        """The spec's bindings read from the live tree, `{out}` bound to that live tree: every render of one core
        is byte-identical wherever it is written, so a base and a candidate differ only where the core does."""
        live = self._home / RunService.spec(tree, backend)["tree"]
        return await RunService.bindings(RunService.spec(tree, backend), live) | {"out": str(live)}

    ############################################################

    ##### PUBLIC #####

    async def plan(self, source: Path, backend: str, out: Path) -> tuple[NousTree, Projection]:
        """`source` projected for `backend`, bound as `project` binds it: the tree it read and the projection.
        Writes nothing."""
        nous = GitNous(source, None)
        tree = await nous.load()
        return await self._runner.project(nous, backend, out, await self._common_bindings(tree, backend))

    async def project(self, source: Path, backend: str, out: Path) -> tuple[NousTree, Projection]:
        """`source` exported for `backend` into a fresh `out`: the tree it read and the projection it wrote."""
        await anyio.to_thread.run_sync(lambda: shutil.rmtree(out, ignore_errors=True))
        nous = GitNous(source, None)
        tree = await nous.load()
        return tree, await self._runner.run(nous, backend, out, await self._common_bindings(tree, backend))

    async def run(self, context: PlaneContext) -> Outcome:
        state = context.state
        tree = context.param("tree", WORKING)
        source = state.paths.sandbox if tree == SANDBOX else Path(state.manifest.tree)
        _, projection = await self.project(source, state.manifest.backend, state.paths.base)
        files = len(projection.files)
        return Outcome(
            status=Status.OK,
            metrics=RenderMetrics(out=str(state.paths.base), backend=state.manifest.backend, files=files, tree=tree),
        )
