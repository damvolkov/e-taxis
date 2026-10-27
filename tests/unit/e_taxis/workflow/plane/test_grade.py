"""tests/unit/e_taxis/workflow/plane/grade: the matrix weighs what moved — a persona block by the slot it carries, a new
entity by its lifecycle, a slot the matrix does not judge stops the grade."""

import shutil
from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.models.placement import Placement
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.metrics import GradeMetrics
from e_taxis.workflow.models.plane import Cadence, NodeCard, NodeSpec, Role, Target
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.plane.grade import kind_grade, slot_grade

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

SKILL = "core/tekton/skills/algo-py-core"
GRADE = NodeSpec(id="grade", use="grade", card=NodeCard(role=Role.GATE, summary="g"))


@pytest.mark.parametrize(
    ("entity", "fragment", "owner", "slot"),
    [
        (Entity.PERSONA, "Voice", Placement("CLAUDE.md", "Voice", "v", "persona", 9, ("voice",)), "voice"),
        (Entity.AGENT, "body", None, "prompt"),
        (Entity.TOOL, "body", None, "body"),
        (Entity.SKILL, "fm.description", None, "description"),
        (Entity.SKILL, "title", None, "name"),
        (Entity.AGENT, "preload", None, "skills"),
    ],
    ids=["persona", "agent-body", "unknown-body", "frontmatter", "title", "preload"],
)
async def test_grade_slot(entity: Entity, fragment: str, owner: Placement | None, slot: str) -> None:
    assert slot_grade(entity, fragment, owner) == slot


@pytest.mark.parametrize(
    ("before", "after", "kind"),
    [(None, b"x", "added"), (b"x", None, "removed"), (b"x", b"y", "changed")],
    ids=["added", "removed", "changed"],
)
async def test_grade_kind(before: bytes | None, after: bytes | None, kind: str) -> None:
    assert kind_grade(before, after) == kind


async def test_grade_persona_block_by_its_slot(plane_run: PlaneRun, plane_nous: Path) -> None:
    method = plane_nous / "core/tekton/persona/praxis/method.md"
    method.write_text(method.read_text() + "\nOne more method.\n")
    report = await plane_run.enhance(plane_nous, Target.PERSONA, ("persona",), Cadence.COMMIT, manual=True)
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert isinstance(grade.metrics, GradeMetrics)
    assert grade.status is Status.OK
    assert grade.metrics.grade == "guidance"
    assert ("method",) in [change.slots for change in grade.metrics.changes]


async def test_grade_a_new_skill_is_its_lifecycle(plane_run: PlaneRun, plane_nous: Path) -> None:
    born = plane_nous / "core/tekton/skills/algo-py-born"
    shutil.copytree(plane_nous / SKILL, born)
    manifest = born / "skill.yaml"
    manifest.write_text(manifest.read_text().replace("name: algo-py-core", "name: algo-py-born"))
    report = await plane_run.enhance(plane_nous, Target.SKILL, ("algo-py-born",), Cadence.COMMIT, manual=True)
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert isinstance(grade.metrics, GradeMetrics)
    kinds = {change.path: (change.kind, change.grade) for change in grade.metrics.changes}
    assert kinds["skills/algo-py-born/SKILL.md"] == ("added", "surface")
    assert kinds["skills/algo-py-born/references/lib.md"] == ("added", "deepening")
    assert grade.metrics.grade == "surface"


async def test_grade_unjudged_slot_stops(
    plane_run: PlaneRun, plane_nous: Path, commit: Callable[..., Awaitable[str]]
) -> None:
    matrix = plane_nous / "core/versioning/matrix.yaml"
    matrix.write_text(matrix.read_text().replace("    instructions: guidance", "    instruction_was: guidance", 1))
    await commit(plane_nous, "matrix behind the corpus")
    body = plane_nous / SKILL / "instructions.md"
    body.write_text(body.read_text() + "\nNew rule.\n")
    report = await plane_run.enhance(plane_nous, Target.SKILL, ("algo-py-core",), Cadence.COMMIT, manual=True)
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert grade.status is Status.FAIL
    assert grade.reason.startswith("the matrix does not judge skill:instructions")


async def test_grade_without_candidate_skips(
    plane_nodes: dict[str, Any], plane_state: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    outcome = await plane_nodes["grade"].run(plane_context(await plane_state(GRADE), "grade"))
    assert (outcome.status, outcome.reason) == (Status.SKIP, "no candidate render")
