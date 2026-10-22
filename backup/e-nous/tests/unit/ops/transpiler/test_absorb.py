"""Unit tests for absorb: what a harness wrote into its persona files, folded back into a copy of core/.

Every test runs on a copy of the corpus and a throwaway harness tree: the live harness and
the repo's core/ are never read for writing, never written.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.transpiler.absorb import Absorb, AbsorbReport, Take
from ops.transpiler.render import Transpiler

REGION = "<!-- openhuman:goals:start -->\n## Goals\n\n- ship\n\n<!-- openhuman:goals:end -->"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """core/ and specs/ copied, a few slots given short, known text."""
    root = tmp_path / "repo"
    for name in ("core", "specs"):
        shutil.copytree(settings.ROOT / name, root / name)
    (root / "core/nomos/persona/character/face.md").write_text("Calm under fire.\n")
    (root / "core/nomos/persona/praxis/modes.md").write_text("- engineer\n- researcher\n")
    (root / "core/base/persona/bond/profile.md").write_text("Seville. Spanish.\n")
    return root


@pytest.fixture
def harness(repo: Path, tmp_path: Path) -> tuple[Transpiler, dict[str, str]]:
    """The render landed in a throwaway harness and recorded as its base point."""
    render = Transpiler(repo, Backend.OPENHUMAN, tmp_path / "harness")
    render.export()
    return render, {doc.target: (render.out / doc.target).read_text() for doc in render.documents}


def _edit(render: Transpiler, target: str, old: str, new: str) -> None:
    path = render.out / target
    assert old in (text := path.read_text()), f"{old!r} not in {target}"
    path.write_text(text.replace(old, new))


def _fresh(render: Transpiler) -> Transpiler:
    """A new render over the same root: core/ re-read, nothing cached."""
    return Transpiler(render.root, render.backend, render.out)


def _absorb(render: Transpiler, recorded: dict[str, str] | None, take: Take = "recorded") -> AbsorbReport:
    return Absorb(_fresh(render), recorded, take).run()


# ------------------------------------------------------------------- settled
def test_a_harness_nobody_touched_absorbs_nothing(harness: tuple[Transpiler, dict[str, str]]) -> None:
    report = _absorb(*harness)
    assert report.empty and report.held == ()


# ------------------------------------------------------------------- harness
def test_a_harness_edit_lands_in_its_slot(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    _edit(render, "memory/persona/SOUL.md", "Calm under fire.", "Calm under fire, hard on ideas.")
    report = _absorb(render, recorded)
    assert [(s.slot, s.path, s.after) for s in report.slots] == [
        ("face", "core/nomos/persona/character/face.md", "Calm under fire, hard on ideas.")
    ]


def test_an_edit_inside_a_shared_block_finds_its_slot(harness: tuple[Transpiler, dict[str, str]]) -> None:
    """Personality joins temperament, face and critique: the edit to critique goes to base, the others stay."""
    render, recorded = harness
    _edit(render, "memory/persona/SOUL.md", "Agreement must be earned.", "Agreement must be earned, never granted.")
    assert [(s.slot, s.path) for s in _absorb(render, recorded).slots] == [
        ("critique", "core/base/persona/logos/critique.md")
    ]


def test_text_written_under_an_empty_slot_heading_fills_that_slot(harness: tuple[Transpiler, dict[str, str]]) -> None:
    """Commitments is empty, so its heading is not rendered; the harness adding it fills the slot."""
    render, recorded = harness
    path = render.out / "memory/persona/IDENTITY.md"
    path.write_text(path.read_text() + "\n\n## Commitments\n\nParrhesia over comfort.")
    assert [(s.slot, s.after) for s in _absorb(render, recorded).slots] == [("commitments", "Parrhesia over comfort.")]


def test_write_lands_the_slot_and_the_render_reproduces_the_harness(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    _edit(render, "memory/persona/ROLE.md", "- researcher", "- researcher\n- interlocutor")
    absorb = Absorb(_fresh(render), recorded)
    written = absorb.write(absorb.run())
    assert written == (render.root / "core/nomos/persona/praxis/modes.md",)
    assert written[0].read_text() == "- engineer\n- researcher\n- interlocutor\n"
    assert (
        _fresh(render).files[render.out / "memory/persona/ROLE.md"]
        == (render.out / "memory/persona/ROLE.md").read_text()
    )


# ---------------------------------------------------------------- held back
def test_a_block_core_moved_is_left_to_the_export(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    (render.root / "core/nomos/persona/praxis/modes.md").write_text("- engineer\n")
    report = _absorb(render, recorded)
    assert report.empty and [(b.block, b.direction) for b in report.held] == [("Modes", "core")]


def test_a_block_both_sides_moved_is_held_unless_the_harness_is_taken(
    harness: tuple[Transpiler, dict[str, str]],
) -> None:
    render, recorded = harness
    (render.root / "core/nomos/persona/praxis/modes.md").write_text("- engineer\n- researcher\n- writer\n")
    _edit(render, "memory/persona/ROLE.md", "- researcher", "- researcher\n- poet")
    held = _absorb(render, recorded)
    assert held.empty and [(b.block, b.direction) for b in held.held] == [("Modes", "diverged")]
    taken = _absorb(render, recorded, "harness")
    assert [(s.slot, s.after) for s in taken.slots] == [("modes", "- engineer\n- researcher\n- poet")]


def test_a_heading_no_block_declares_is_unplaced(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    path = render.out / "memory/persona/SOUL.md"
    path.write_text(path.read_text() + "\n\n## Hobbies\n\nDrone flute.")
    report = _absorb(render, recorded)
    assert report.empty and [(b.block, b.direction) for b in report.held] == [("## Hobbies", "unplaced")]


def test_an_inline_slot_is_named_never_written(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    _edit(render, "memory/persona/SOUL.md", "# Demian", "# Demian the daimon")
    report = _absorb(render, recorded)
    assert report.empty and [(b.block, b.reason) for b in report.held] == [
        ("name", "inline in its manifest: edit persona.yaml by hand")
    ]


def test_an_edit_across_two_slots_is_held(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    _edit(render, "memory/persona/SOUL.md", "Calm under fire.\n\n- Critique", "Calm under fire. - Critique")
    report = _absorb(render, recorded)
    assert report.empty and [(b.block, b.direction) for b in report.held] == [("Personality", "held")]


def test_an_unbased_harness_is_held_unless_taken(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, _ = harness
    _edit(render, "memory/persona/SOUL.md", "Calm under fire.", "Calm.")
    assert _absorb(render, None).empty
    assert [s.slot for s in _absorb(render, None, "harness").slots] == ["face"]


def test_a_missing_document_is_named(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    (render.out / "memory/persona/STYLE.md").unlink()
    assert ("memory/persona/STYLE.md", "absent from the harness") in {
        (b.document, b.reason) for b in _absorb(render, recorded).held
    }


# ------------------------------------------------------------------- regions
def test_what_the_learner_writes_is_learned_never_absorbed(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, recorded = harness
    path = render.out / "memory/persona/PROFILE.md"
    path.write_text(path.read_text() + "\n\n" + REGION + "\n")
    report = _absorb(render, recorded)
    assert report.empty and report.held == () and report.learned == (REGION,)


def test_an_export_keeps_the_learners_region(harness: tuple[Transpiler, dict[str, str]]) -> None:
    render, _ = harness
    path = render.out / "memory/persona/PROFILE.md"
    path.write_text(path.read_text() + "\n\n" + REGION + "\n")
    (render.root / "core/base/persona/bond/profile.md").write_text("Seville. Spanish. Rust.\n")
    _fresh(render).export()
    assert path.read_text() == "Seville. Spanish. Rust.\n\n" + REGION


# --------------------------------------------------------------------- coder
def test_the_coder_harness_absorbs_into_base(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    for name in ("core", "specs"):
        shutil.copytree(settings.ROOT / name, root / name)
    render = Transpiler(root, Backend.CLAUDECODE, tmp_path / "claude")
    render.export()
    recorded = {"CLAUDE.md": (render.out / "CLAUDE.md").read_text()}
    _edit(render, "CLAUDE.md", "Never a soft story.", "Never a soft story, never a hedge.")
    assert [(s.slot, s.path) for s in _absorb(render, recorded).slots] == [
        ("honesty", "core/base/persona/logos/honesty.md")
    ]
