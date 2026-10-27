"""plane.candidate: one subject's candidate — its own tree (a clone at the base with only its change overlaid from the
sandbox), rendered with the v2 engine into its own folder, and the rendered paths it moved against the base render.

Every moved path is the subject's by construction: siblings enhanced in the same run never reach its tree. A spec's
product is its source, so a spec subject also counts the source paths that moved (rows the render does not read yet
still change the spec). Empty means no proposer moved anything: the subject is settled.

The fixpoint is v2's own round trip, byte for byte: every moved file, read back through its target's format
(`engine.reverse` over the written bytes, with no landing as base), must yield exactly the fragments its placements
rendered. v1 proved `reverse(view(skill)) == skill` on skills alone; this holds every target kind to the same law. A
path that does not read back is `unread`, and the gate is red."""

from typing import TYPE_CHECKING, ClassVar

import anyio

from e_taxis.transpile.engine.encode import match_target
from e_taxis.transpile.engine.reverse import classify_reverse
from e_taxis.transpile.services.run import RunService
from e_taxis.workflow.models.metrics import CandidateMetrics
from e_taxis.workflow.models.plane import Guard, NodeCard, Role, Target
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.models.ports import PlaneContext, SandboxPort
    from e_taxis.workflow.plane.render import PlaneRender

##### DEFAULTS #####
BROKEN: str = "the candidate does not read back: fixpoint broken"


##### UTILITIES #####
def files_of(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by its path from it; empty when `root` is not there."""
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


##### TYPES #####
class PlaneCandidate:
    """Satisfies PlaneNodePort over the base render's own projector and the sandbox."""

    __slots__ = ("_render", "_sandbox")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="the subject's candidate render, what it moved, its v2 fixpoint", guard=Guard.SETTLED
    )

    def __init__(self, render: PlaneRender, sandbox: SandboxPort) -> None:
        self._render = render
        self._sandbox = sandbox

    async def run(self, context: PlaneContext) -> Outcome:
        manifest, paths = context.state.manifest, context.state.paths
        place, subject = manifest.place(context.subject), context.subject
        tree = await self._sandbox.open(paths.sandbox, paths.tree(subject), manifest.base_sha)
        await self._sandbox.overlay(paths.sandbox, tree, place)
        out = paths.candidate(subject)
        nous, projection = await self._render.project(tree, manifest.backend, out)
        base, cand = await anyio.to_thread.run_sync(files_of, paths.base), await anyio.to_thread.run_sync(files_of, out)
        sources = await self._sandbox.changed(tree, manifest.base_sha, place) if manifest.target is Target.SPEC else ()
        moved = {path for path in base.keys() | cand.keys() if base.get(path) != cand.get(path)}
        spec = RunService.spec(nous, manifest.backend)
        unread = tuple(
            sorted(
                path
                for path in moved & projection.placements.keys()
                if any(
                    classify_reverse(
                        spec,
                        path,
                        match_target(path, spec["targets"]),
                        projection.placements[path],
                        live=cand[path],
                        base=None,
                    )
                )
            )
        )
        metrics = CandidateMetrics(
            out=str(out), changed=tuple(sorted(moved | set(sources))), fixpoint=not unread, unread=unread
        )
        return Outcome(status=Status.FAIL if unread else Status.OK, metrics=metrics, reason=BROKEN if unread else "")
