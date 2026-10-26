"""Unit tests for the equivalence matrix: entity + slot ⇒ grade ⇒ bump.

The matrix is the only thing that decides how much a change weighs, and it decides it
without a model. These tests assert the verdicts, never how they were reached — and the
coverage gate at the end is the one that keeps the table honest as the corpus grows.
"""

from __future__ import annotations

import pytest

from ops.models.entity import INSTANCED, Backend, Entity
from ops.transpiler.history.matrix import Matrix, UnknownSlotError
from ops.transpiler.render import Transpiler


@pytest.fixture
def matrix() -> Matrix:
    """The shipped table in core/versioning."""
    return Matrix()


# ------------------------------------------------------------------- shipped
def test_matrix_loads_the_shipped_scale(matrix: Matrix) -> None:
    assert [grade.name for grade in matrix.grades] == [
        "cosmetic",
        "deepening",
        "guidance",
        "routing",
        "surface",
        "contract",
    ]


def test_matrix_levels_are_unique_and_ordered(matrix: Matrix) -> None:
    levels = [grade.level for grade in matrix.grades]
    assert levels == sorted(levels) == sorted(set(levels))


def test_matrix_grades_carry_their_own_documentation(matrix: Matrix) -> None:
    """The table is its own doc: a grade nobody can read is a grade nobody will apply."""
    assert all(grade.description and grade.example for grade in matrix.grades)


def test_matrix_declares_a_lifecycle_for_every_entity_it_grades(matrix: Matrix) -> None:
    assert set(matrix.slots) <= set(matrix.lifecycle)


# -------------------------------------------------------------- slot verdicts
@pytest.mark.parametrize(
    ("entity", "slot", "expected"),
    [
        (Entity.SKILL, "description", "routing"),
        (Entity.SKILL, "name", "routing"),
        (Entity.SKILL, "instructions", "guidance"),
        (Entity.SKILL, "references/antipatterns.md", "deepening"),
        (Entity.SKILL, "metadata", "cosmetic"),
        (Entity.AGENT, "prompt", "guidance"),
        (Entity.AGENT, "mode", "contract"),
        (Entity.AGENT, "permission", "contract"),
        (Entity.COMMAND, "template", "guidance"),
        (Entity.COMMAND, "agent", "contract"),
        (Entity.PERSONA, "soul", "guidance"),
        (Entity.PERSONA, "epigraph", "cosmetic"),
        (Entity.CONFIG, "mcp", "contract"),
        (Entity.CONFIG, "username", "cosmetic"),
    ],
    ids=[
        "skill-description",
        "skill-name",
        "skill-instructions",
        "skill-reference",
        "skill-metadata",
        "agent-prompt",
        "agent-mode",
        "agent-permission",
        "command-template",
        "command-agent",
        "persona-soul",
        "persona-epigraph",
        "config-mcp",
        "config-username",
    ],
)
def test_slot_grades_at_its_declared_level(matrix: Matrix, entity: Entity, slot: str, expected: str) -> None:
    assert matrix.of(entity, "changed", (slot,)).name == expected


def test_the_same_slot_name_weighs_differently_per_entity(matrix: Matrix) -> None:
    """`instructions` is a skill's rules and a config's boot-time context files. Never one rule for both."""
    assert matrix.of(Entity.SKILL, "changed", ("instructions",)).name == "guidance"
    assert matrix.of(Entity.CONFIG, "changed", ("instructions",)).name == "contract"


def test_several_slots_take_the_heaviest(matrix: Matrix) -> None:
    """A change weighs what its worst slot weighs, never its average."""
    slots = ("references/lib.md", "instructions", "description")
    assert matrix.of(Entity.SKILL, "changed", slots).name == "routing"


# ----------------------------------------------------------------- lifecycle
def test_a_new_skill_is_surface(matrix: Matrix) -> None:
    assert matrix.of(Entity.SKILL, "added").name == "surface"


def test_a_removed_skill_breaks_a_contract(matrix: Matrix) -> None:
    assert matrix.of(Entity.SKILL, "removed").name == "contract"


def test_a_new_config_file_is_already_a_contract(matrix: Matrix) -> None:
    """Unlike a skill: a config file that appears changes how the coder boots."""
    assert matrix.of(Entity.CONFIG, "added").name == "contract"


def test_lifecycle_outweighs_a_cosmetic_slot(matrix: Matrix) -> None:
    assert matrix.of(Entity.SKILL, "removed", ("metadata",)).name == "contract"


# ------------------------------------------------------------------ the floor
def test_an_undeclared_slot_is_refused_not_assumed(matrix: Matrix) -> None:
    """A slot the corpus grew and the table has not judged must stop the ledger, not slip through as a patch."""
    with pytest.raises(UnknownSlotError, match="invented"):
        matrix.of(Entity.SKILL, "changed", ("invented",))


def test_a_slot_declared_for_another_entity_is_still_refused(matrix: Matrix) -> None:
    """`mode` is an agent's; a skill growing one would be news, not a patch."""
    with pytest.raises(UnknownSlotError):
        matrix.of(Entity.SKILL, "changed", ("mode",))


def test_a_change_with_no_slot_at_all_is_cosmetic(matrix: Matrix) -> None:
    assert matrix.of(Entity.SKILL, "changed", ()).name == "cosmetic"


# --------------------------------------------------------------------- bumps
@pytest.mark.parametrize(
    ("grades", "expected"),
    [
        ((), "none"),
        (("cosmetic",), "patch"),
        (("deepening",), "patch"),
        (("guidance",), "minor"),
        (("routing",), "minor"),
        (("surface",), "minor"),
        (("contract",), "major"),
        (("cosmetic", "guidance"), "minor"),
        (("deepening", "contract", "routing"), "major"),
    ],
    ids=[
        "nothing",
        "cosmetic",
        "deepening",
        "guidance",
        "routing",
        "surface",
        "contract",
        "patch-and-minor",
        "anything-with-major",
    ],
)
def test_bump_is_the_heaviest_of_its_grades(matrix: Matrix, grades: tuple[str, ...], expected: str) -> None:
    assert matrix.bump(grades) == expected


def test_bump_refuses_a_grade_the_table_does_not_declare(matrix: Matrix) -> None:
    with pytest.raises(KeyError):
        matrix.bump(("invented",))


# ------------------------------------------------------------- coverage gate
def _emitted(entity: Entity) -> frozenset[str]:
    """Every slot any backend can emit: the table is one doctrine for all of them."""
    return frozenset().union(*(Transpiler(backend=backend).emitted(entity) for backend in Backend))


@pytest.mark.parametrize("entity", [*INSTANCED, Entity.PERSONA, Entity.CONFIG], ids=str)
def test_matrix_judges_every_slot_the_transpiler_can_emit(matrix: Matrix, entity: Entity) -> None:
    """The gate that keeps the table honest: grow a slot in a spec and this fails until it is graded."""
    assert _emitted(entity) <= matrix.declared(entity), (
        f"{entity}: ungraded {_emitted(entity) - matrix.declared(entity)}"
    )


@pytest.mark.parametrize("entity", [*INSTANCED, Entity.PERSONA, Entity.CONFIG], ids=str)
def test_matrix_grades_nothing_the_transpiler_cannot_emit(matrix: Matrix, entity: Entity) -> None:
    """The mirror: a row for a slot that no backend emits any more is doctrine about nothing."""
    families = {slot for slot in matrix.declared(entity) if "*" in slot}
    assert matrix.declared(entity) - families <= _emitted(entity) or not _emitted(entity)
