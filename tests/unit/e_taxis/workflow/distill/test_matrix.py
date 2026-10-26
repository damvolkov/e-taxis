"""tests/unit/e_taxis/workflow/distill/matrix: the versioning matrix as grade reads it — heaviest slot, lifecycle, gaps."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import DistillError, UnknownSlotError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("entity", "kind", "slots", "grade"),
    [
        (Entity.SKILL, "changed", ("references/x.md",), "deepening"),
        (Entity.SKILL, "changed", ("instructions", "references/x.md"), "guidance"),
        (Entity.SKILL, "added", (), "surface"),
        (Entity.AGENT, "removed", ("prompt",), "contract"),
        (Entity.SKILL, "changed", (), "cosmetic"),
    ],
    ids=["family", "heaviest", "added", "removed", "nothing"],
)
async def test_matrix_of(matrix: VersionMatrix, entity: Entity, kind, slots: tuple[str, ...], grade: str) -> None:
    assert matrix.of(entity, kind, slots).name == grade


async def test_matrix_unknown_slot_and_grade(matrix: VersionMatrix) -> None:
    with pytest.raises(UnknownSlotError, match="skill:ghost"):
        matrix.of(Entity.SKILL, "changed", ("ghost",))
    with pytest.raises(KeyError, match="no such grade"):
        matrix["ghost"]


async def test_matrix_load(tmp_path: Path) -> None:
    with pytest.raises(DistillError, match="no versioning matrix"):
        await VersionMatrix.load(tmp_path / "matrix.yaml")
    (tmp_path / "matrix.yaml").write_text(
        "grades: [{name: a, level: 0, bump: patch, description: d}]\nlifecycle: {}\nslots: {skill: {x: a}}\n"
    )
    assert (await VersionMatrix.load(tmp_path / "matrix.yaml")).of(Entity.SKILL, "changed", ("x",)).name == "a"
