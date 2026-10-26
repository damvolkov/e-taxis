"""Unit tests for typeset: one document spec, read both ways — slots to text and spans, text to blocks, regions apart."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.models.spec import Block, Document, Region
from ops.transpiler.render import Transpiler
from ops.transpiler.typeset import Typeset

MARKER = Region(kind="marker", start="<!-- oh:(?P<b>[a-z]+):start -->", end="<!-- oh:(?P=b):end -->")
DOC = Document(
    target="SOUL.md",
    limit=200,
    blocks=[
        Block(type="h1", slots=["name"]),
        Block(type="para", slots=["essence"]),
        Block(type="quote", slots=["epigraph"]),
        Block(type="h2", heading="Voice", slots=["voice", "critique"], join="\n"),
        Block(type="h2", heading="Modes", slots=["modes"]),
    ],
    regions=[MARKER, Region(kind="heading", match="About You")],
)
SLOTS = {
    "name": "Demian",
    "essence": "The daimon.",
    "epigraph": "Der Vogel.",
    "voice": "- terse\n",
    "critique": "- honest\n",
    "modes": "",
}
RENDERED = "# Demian\n\nThe daimon.\n\n> Der Vogel.\n\n## Voice\n\n- terse\n- honest"


@pytest.fixture
def typeset() -> Typeset:
    return Typeset(DOC)


# -------------------------------------------------------------------- render
def test_render_joins_blocks_and_skips_an_empty_block(typeset: Typeset) -> None:
    assert typeset.render(SLOTS) == RENDERED


def test_render_spans_point_at_each_slot(typeset: Typeset) -> None:
    spans = typeset.spans(SLOTS)
    assert {slot: RENDERED[a:b] for slot, (a, b) in spans.items()} == {
        "name": "Demian",
        "essence": "The daimon.",
        "epigraph": "Der Vogel.",
        "voice": "- terse",
        "critique": "- honest",
    }


def test_render_refuses_past_the_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        Typeset(Document(target="X.md", limit=3, blocks=[Block(type="para", slots=["a"])])).render({"a": "toolong"})


def test_render_refuses_a_slot_no_layer_declares(typeset: Typeset) -> None:
    with pytest.raises(ValueError, match="declared by no layer"):
        typeset.render({"name": "Demian"})


def test_render_of_nothing_is_empty() -> None:
    assert Typeset(Document(target="X.md", blocks=[Block(type="para", slots=["a"])])).render({"a": ""}) == ""


# --------------------------------------------------------------------- parse
def test_parse_reads_the_render_back_into_its_blocks(typeset: Typeset) -> None:
    assert typeset.parse(RENDERED) == {
        "h1": "Demian",
        "para": "The daimon.",
        "quote": "Der Vogel.",
        "Voice": "- terse\n- honest",
    }


def test_parse_keeps_an_undeclared_heading_apart(typeset: Typeset) -> None:
    assert typeset.parse(RENDERED + "\n\n## Learned\n\nx")["## Learned"] == "x"


# ------------------------------------------------------------------- regions
def test_regions_are_cut_and_the_gap_closed(typeset: Typeset) -> None:
    live = RENDERED + "\n\n<!-- oh:style:start -->\n## Style\n- terse\n<!-- oh:style:end -->\n"
    assert typeset.strip(live) == RENDERED


def test_a_heading_region_runs_to_the_next_heading(typeset: Typeset) -> None:
    live = "# Demian\n\n## About You\n\nfrom the editor\n\n## Voice\n\n- terse"
    assert typeset.strip(live) == "# Demian\n\n## Voice\n\n- terse"


def test_merge_carries_the_live_regions_after_the_render(typeset: Typeset) -> None:
    region = "<!-- oh:goals:start -->\n- ship\n<!-- oh:goals:end -->"
    merged = typeset.merge(RENDERED, f"old text\n\n{region}\n")
    assert merged == f"{RENDERED}\n\n{region}" and typeset.strip(merged) == RENDERED


def test_merge_without_regions_is_the_render(typeset: Typeset) -> None:
    assert typeset.merge(RENDERED, "anything") == RENDERED


def test_merge_never_drops_an_undeclared_heading_the_live_file_holds(typeset: Typeset) -> None:
    merged = typeset.merge(RENDERED, "## Voice\n\n- old\n\n## Taste\n\n- plain\n")
    assert merged == f"{RENDERED}\n\n## Taste\n\n- plain" and typeset.parse(merged)["Voice"] == "- terse\n- honest"


# ----------------------------------------------------------- harness layers
def test_tekton_renders_base_and_tekton_never_nomos(tmp_path: Path) -> None:
    slots = Transpiler(settings.ROOT, Backend.OPENCODE, tmp_path).persona
    assert {"origin", "soul", "contract"} <= set(slots) and not {"commitments", "craft"} & set(slots)


def test_nomos_renders_base_and_nomos_never_tekton(tmp_path: Path) -> None:
    slots = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path).persona
    assert {"about", "temperament", "face", "craft"} <= set(slots) and not {"origin", "soul", "contract"} & set(slots)


def test_the_polymath_spec_lands_every_document(tmp_path: Path) -> None:
    """Six documents and the config, slots placed, nothing truncated."""
    files = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path).files
    assert {path.name for path in files} == {
        "SOUL.md",
        "IDENTITY.md",
        "ROLE.md",
        "STYLE.md",
        "AGENTS.md",
        "PROFILE.md",
        "config.toml",
    }
    soul = files[(tmp_path / "memory/persona/SOUL.md").resolve()]
    assert soul.startswith("# Demian") and "## About You" in soul and "## Voice" not in soul


def test_a_slot_in_two_layers_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(settings.ROOT / "core", root / "core")
    nomos = root / "core/nomos/persona.yaml"
    nomos.write_text(nomos.read_text() + "  honesty: {source: persona/ethos/limits.md}\n")
    with pytest.raises(ValueError, match="more than one layer"):
        _ = Transpiler(root, Backend.OPENHUMAN, tmp_path / "out").persona
