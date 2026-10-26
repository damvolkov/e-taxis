"""Unit tests for the classifier: a flat path read back into the entity it belongs to.

This is the piece that turns `M skills/test-py-tdd/SKILL.md` into "skill test-py-tdd,
rule body moved, guidance". It knows nothing by hand: every route is inverted from the
spec the transpiler already obeys.
"""

from __future__ import annotations

import pytest

from ops.models.entity import Entity
from ops.models.history import FileChange
from ops.transpiler.history.classify import Classifier
from ops.transpiler.render import Transpiler

FRONTMATTER = "---\nname: test-py-tdd\ndescription: old one\n---\n\n# test-py-tdd\n\nrule one\n"


@pytest.fixture
def classifier() -> Classifier:
    """The classifier bound to the shipped specs."""
    return Classifier(Transpiler())


# ------------------------------------------------------------------- routing
@pytest.mark.parametrize(
    ("path", "entity", "ident"),
    [
        ("skills/test-py-tdd/SKILL.md", Entity.SKILL, "test-py-tdd"),
        ("skills/test-py-tdd/references/lib.md", Entity.SKILL, "test-py-tdd"),
        ("agents/builder.md", Entity.AGENT, "builder"),
        ("commands/audit.md", Entity.COMMAND, "audit"),
        ("AGENTS.md", Entity.PERSONA, ""),
        ("opencode.jsonc", Entity.CONFIG, ""),
        ("tui.json", Entity.CONFIG, ""),
        ("package.json", Entity.CONFIG, ""),
    ],
    ids=["skill", "skill-reference", "agent", "command", "persona", "opencode", "tui", "package"],
)
def test_locate_reads_the_path_back_into_its_entity(
    classifier: Classifier, path: str, entity: Entity, ident: str
) -> None:
    site = classifier.locate(path)
    assert site is not None and site.entity is entity and site.id == ident


def test_locate_names_the_config_file_as_the_subentity(classifier: Classifier) -> None:
    """config is one entity with several faces; the file it lands in is which face."""
    site = classifier.locate("opencode.jsonc")
    assert site is not None and site.subentity == "opencode.jsonc"


def test_locate_treats_a_reference_as_a_slot_of_its_skill(classifier: Classifier) -> None:
    site = classifier.locate("skills/test-py-tdd/references/antipatterns.md")
    assert site is not None and site.slot == "references/antipatterns.md"


def test_locate_ignores_what_no_spec_claims(classifier: Classifier) -> None:
    """Runtime trees and strangers are not corpus; the ledger must not invent an entity for them."""
    assert classifier.locate("sessions/live.json") is None
    assert classifier.locate("skills/synced/ghost/SKILL.md") is None


# --------------------------------------------------------------------- slots
def test_a_changed_description_is_the_description_slot(classifier: Classifier) -> None:
    after = FRONTMATTER.replace("old one", "a new one")
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "changed"), FRONTMATTER, after)
    assert change.pointers == ("/description",)
    assert change.grade == "routing"


def test_a_changed_body_is_the_body_slot(classifier: Classifier) -> None:
    after = FRONTMATTER.replace("rule one", "rule one, rewritten")
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "changed"), FRONTMATTER, after)
    assert change.pointers == ("/instructions",)
    assert change.grade == "guidance"


def test_several_slots_are_all_reported_and_the_grade_is_the_heaviest(classifier: Classifier) -> None:
    after = FRONTMATTER.replace("old one", "a new one").replace("rule one", "rewritten")
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "changed"), FRONTMATTER, after)
    assert sorted(change.pointers) == ["/description", "/instructions"]
    assert change.grade == "routing"


def test_a_slot_that_appeared_is_reported(classifier: Classifier) -> None:
    after = FRONTMATTER.replace("description: old one", "description: old one\nlicense: MIT")
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "changed"), FRONTMATTER, after)
    assert change.pointers == ("/license",)


def test_an_untouched_file_reports_no_slot(classifier: Classifier) -> None:
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "changed"), FRONTMATTER, FRONTMATTER)
    assert change.pointers == ()
    assert change.grade == "cosmetic"


# ----------------------------------------------------------------- lifecycle
def test_a_new_skill_weighs_as_a_new_surface(classifier: Classifier) -> None:
    change = classifier.of(FileChange("skills/brand-new/SKILL.md", "added"), "", FRONTMATTER)
    assert change.kind == "added" and change.grade == "surface"


def test_a_removed_skill_breaks_a_contract(classifier: Classifier) -> None:
    change = classifier.of(FileChange("skills/test-py-tdd/SKILL.md", "removed"), FRONTMATTER, "")
    assert change.grade == "contract"


def test_a_new_reference_is_depth_not_a_new_entity(classifier: Classifier) -> None:
    """The skill already existed; it grew a reference. Deepening, never surface."""
    change = classifier.of(FileChange("skills/test-py-tdd/references/antipatterns.md", "added"), "", "# antipatterns\n")
    assert change.grade == "deepening"
    assert change.pointers == ("/references/antipatterns.md",)


def test_a_removed_reference_is_still_depth(classifier: Classifier) -> None:
    change = classifier.of(FileChange("skills/test-py-tdd/references/old.md", "removed"), "# old\n", "")
    assert change.grade == "deepening"


# -------------------------------------------------------------------- config
def test_a_changed_config_key_names_that_key(classifier: Classifier) -> None:
    before, after = '{"username": "damien", "mcp": {"a": 1}}', '{"username": "damien", "mcp": {"a": 2}}'
    change = classifier.of(FileChange("opencode.jsonc", "changed"), before, after)
    assert change.pointers == ("/mcp",)
    assert change.grade == "contract"


def test_a_cosmetic_config_key_stays_cosmetic(classifier: Classifier) -> None:
    before, after = '{"username": "damien"}', '{"username": "dam"}'
    change = classifier.of(FileChange("opencode.jsonc", "changed"), before, after)
    assert change.grade == "cosmetic"


# ------------------------------------------------------------------- persona
def test_a_changed_persona_section_is_guidance(classifier: Classifier) -> None:
    before = "# Demian\n\nessence\n\n> epigraph\n\n## Honesty\n\nsay so\n"
    after = "# Demian\n\nessence\n\n> epigraph\n\n## Honesty\n\nsay so, exactly\n"
    change = classifier.of(FileChange("AGENTS.md", "changed"), before, after)
    assert change.pointers == ("/honesty",) and change.grade == "guidance"


def test_a_persona_block_moves_every_slot_it_joins(classifier: Classifier) -> None:
    before = "# Demian\n\nessence\n\n## Voice\n\n- terse\n- critique\n"
    after = "# Demian\n\nessence\n\n## Voice\n\n- terse\n- critique, harder\n"
    change = classifier.of(FileChange("AGENTS.md", "changed"), before, after)
    assert change.pointers == ("/critique", "/voice")


def test_a_heading_no_block_declares_is_unplaced_guidance(classifier: Classifier) -> None:
    before = "# Demian\n\nessence\n"
    after = "# Demian\n\nessence\n\n## Learned\n\nsomething the harness wrote\n"
    change = classifier.of(FileChange("AGENTS.md", "changed"), before, after)
    assert change.pointers == ("/unplaced",) and change.grade == "guidance"


def test_a_changed_persona_essence_is_routing(classifier: Classifier) -> None:
    before = "# Demian\n\nessence\n\n> epigraph\n\n## Voice\n\nterse\n"
    after = "# Demian\n\nanother essence\n\n> epigraph\n\n## Voice\n\nterse\n"
    change = classifier.of(FileChange("AGENTS.md", "changed"), before, after)
    assert change.pointers == ("/essence",) and change.grade == "routing"
