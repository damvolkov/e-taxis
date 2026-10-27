"""plane.grade: how much the candidate weighs, by `core/versioning/matrix.yaml` and never by a model.

Every moved path is the subject's (the candidate is its own change alone), so the entity is the target's. A path
under `references/` is one of the entity's slots (`references/<file>`); any other is the entity's own file, whose
appearing or vanishing is its lifecycle and whose change is graded by the fragments that moved — the file read back
from the base bytes against what the candidate renders (`fragments_plan`), each fragment named the way the matrix
grades the emitted form: a frontmatter key by its name, the body by the entity's body slot, a persona block by the
slot it carries. The heaviest grade wins; its SemVer bump follows. The matrix is the one the candidate ships with; a
slot it does not judge stops the grade (red): the doctrine is behind the corpus. A spec sits outside the matrix: a
`status:` transition weighs `surface`, any other spec edit `deepening`."""

import re
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final

import anyio

from e_taxis.transpile.engine.encode import match_target
from e_taxis.transpile.engine.plan import fragments_plan
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.services.run import RunService
from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import UnknownSlotError
from e_taxis.workflow.models.metrics import CandidateMetrics, GradedChange, GradeMetrics
from e_taxis.workflow.models.plane import Guard, NodeCard, Role, Target
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from e_taxis.workflow.distill.matrix import Kind
    from e_taxis.workflow.models.ports import PlaneContext, SandboxPort
    from e_taxis.workflow.plane.render import PlaneRender

##### DEFAULTS #####
MATRIX: str = "core/versioning/matrix.yaml"
STATUS: Final[re.Pattern[str]] = re.compile(r"^[+-]status:", re.MULTILINE)
REFERENCES: str = "references"
FRONT: str = "fm."
### the fragment of an entity's own file that is its body, and the matrix slot it is.
BODY: Final[Mapping[Entity, str]] = MappingProxyType(
    {Entity.SKILL: "instructions", Entity.AGENT: "prompt", Entity.COMMAND: "template", Entity.WORKFLOW: "nodes"}
)
### fragments the renders name apart from their matrix slot.
ALIAS: Final[Mapping[str, str]] = MappingProxyType({"title": "name", "preload": "skills"})
SURFACE: str = "surface"
DEEPENING: str = "deepening"


##### UTILITIES #####
def slot_grade(entity: Entity, fragment: str, owner: Placement | None) -> str:
    """The matrix slot one moved fragment of an entity's own file is."""
    match (entity, fragment, owner):
        case (Entity.PERSONA, _, Placement(sources=(slot, *_))):
            return slot
        case (_, "body", _):
            return BODY.get(entity, fragment)
        case _:
            return ALIAS.get(fragment, fragment).removeprefix(FRONT)


def kind_grade(before: bytes | None, after: bytes | None) -> Kind:
    match (before, after):
        case (None, _):
            return "added"
        case (_, None):
            return "removed"
        case _:
            return "changed"


##### TYPES #####
class PlaneGrade:
    """Satisfies PlaneNodePort over the projector and the sandbox."""

    __slots__ = ("_render", "_sandbox")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="versioning grade and bump of the candidate", guard=Guard.SETTLED
    )

    def __init__(self, render: PlaneRender, sandbox: SandboxPort) -> None:
        self._render = render
        self._sandbox = sandbox

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _grade_read(path: Path) -> bytes | None:
        file = anyio.Path(path)
        return await file.read_bytes() if await file.is_file() else None

    @staticmethod
    def _grade_fragments(
        entity: Entity, path: str, before: bytes, placements: tuple[Placement, ...], spec: Mapping[str, Any]
    ) -> tuple[str, ...]:
        """The slots of the fragments that moved between the base bytes and the candidate's render of `path`."""
        target = match_target(path, spec["targets"])
        rendered, found = fragments_plan(target.get("format", "file"), placements, before, target.get("foreign", []))
        owners = {placement.fragment: placement for placement in placements}
        moved = (
            fragment for fragment in rendered.keys() | found.keys() if rendered.get(fragment) != found.get(fragment)
        )
        return tuple(sorted({slot_grade(entity, fragment, owners.get(fragment)) for fragment in moved}))

    @classmethod
    def _grade_change(
        cls,
        matrix: VersionMatrix,
        entity: Entity,
        path: str,
        *,
        pair: tuple[bytes | None, bytes | None],
        placements: tuple[Placement, ...],
        spec: Mapping[str, Any],
    ) -> GradedChange:
        before, after = pair
        kind = kind_grade(before, after)
        name = PurePosixPath(path)
        match (name.parent.name == REFERENCES, kind):
            case (True, _):
                slots, lifecycle = (f"{REFERENCES}/{name.name}",), "changed"
            case (_, "changed"):
                slots, lifecycle = cls._grade_fragments(entity, path, before or b"", placements, spec), "changed"
            case _:
                slots, lifecycle = (), kind
        return GradedChange(path=path, kind=kind, grade=matrix.of(entity, lifecycle, slots).name, slots=slots)

    async def _grade_spec(self, context: PlaneContext, changed: tuple[str, ...]) -> GradeMetrics:
        manifest = context.state.manifest
        tree = context.state.paths.tree(context.subject)
        diff = await self._sandbox.diff(tree, manifest.base_sha, manifest.place(context.subject))
        grade = SURFACE if STATUS.search(diff) else DEEPENING
        matrix = await VersionMatrix.load(tree / MATRIX)
        return GradeMetrics(
            changes=tuple(GradedChange(path=path, kind="changed", grade=grade, slots=()) for path in changed),
            grade=grade,
            bump=matrix[grade].bump,
        )

    async def _grade_entity(self, context: PlaneContext, changed: tuple[str, ...]) -> GradeMetrics:
        manifest, paths = context.state.manifest, context.state.paths
        tree, out = paths.tree(context.subject), paths.candidate(context.subject)
        matrix = await VersionMatrix.load(tree / MATRIX)
        nous, projection = await self._render.plan(tree, manifest.backend, out)
        spec = RunService.spec(nous, manifest.backend)
        entity = Entity(manifest.target.value)
        pairs = {
            path: (await self._grade_read(paths.base / path), await self._grade_read(out / path)) for path in changed
        }
        changes = tuple(
            self._grade_change(
                matrix, entity, path, pair=pair, placements=tuple(projection.placements.get(path, ())), spec=spec
            )
            for path, pair in pairs.items()
        )
        heaviest = max((matrix[change.grade] for change in changes), key=lambda grade: grade.level)
        return GradeMetrics(changes=changes, grade=heaviest.name, bump=heaviest.bump)

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        match context.upstream(context.param("candidate", "candidate")):
            case NodeRun(metrics=CandidateMetrics(changed=())):
                return Outcome(status=Status.IDLE, reason="nothing changed")
            case NodeRun(metrics=CandidateMetrics(changed=changed)) if context.state.manifest.target is Target.SPEC:
                return Outcome(status=Status.OK, metrics=await self._grade_spec(context, changed))
            case NodeRun(metrics=CandidateMetrics(changed=changed)):
                try:
                    metrics = await self._grade_entity(context, changed)
                except UnknownSlotError as unjudged:
                    return Outcome(status=Status.FAIL, reason=f"the matrix does not judge {unjudged.message}")
                return Outcome(status=Status.OK, metrics=metrics)
            case _:
                return Outcome(status=Status.SKIP, reason="no candidate render")
