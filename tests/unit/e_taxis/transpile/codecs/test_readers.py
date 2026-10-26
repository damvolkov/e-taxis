"""tests/unit/e_taxis/transpile/codecs/readers: live bytes read back into the fragments the render compares."""

import pytest

from e_taxis.transpile.codecs.markdown import read_markdown, split_markdown
from e_taxis.transpile.codecs.matter import read_matter, split_matter
from e_taxis.transpile.codecs.structured import MISSING, get_structured, read_json, strays_structured
from e_taxis.transpile.models.placement import Placement


def _at(fragment: str, value: object, glue: str = "\n\n") -> Placement:
    return Placement("t", fragment, value, "s", 0, (), glue)


async def test_readers_markdown_round_trips_its_blocks() -> None:
    placements = [
        _at("h1", "D"),
        _at("para", "lead"),
        _at("quote", "q"),
        _at("Voice", "- a", "\n"),
        _at("Voice", "- b", "\n"),
    ]
    text = "# D\n\nlead\n\n> q\n\n## Voice\n\n- a\n- b"
    assert read_markdown(text) == split_markdown(placements)


async def test_readers_markdown_extra_section_and_no_preamble() -> None:
    assert read_markdown("## A\n\nx\n\n## B\n\ny\n") == {"A": "## A\n\nx", "B": "## B\n\ny"}


async def test_readers_matter_reads_front_title_preload_body() -> None:
    text = "---\nname: x\nlist:\n- a\n---\n\n# x\n\nLoad first: a.\n\nbody text\n"
    wanted = ["fm.name", "title", "preload", "body"]
    assert read_matter(text, wanted) == {
        "fm.name": "x",
        "fm.list": ["a"],
        "title": "x",
        "preload": "Load first: a.",
        "body": "body text",
    }
    assert split_matter([_at("fm.name", "x"), _at("fm.e", []), _at("body", "body text\n")]) == {
        "fm.name": "x",
        "body": "body text",
    }


@pytest.mark.parametrize(
    ("text", "body"),
    [
        ("no front at all\n", "no front at all"),
        ("---\n---\n\nbody\n", "body"),
        ("---\n: [\n---\n\nbody\n", "body"),
        ("---\n- a\n---\n\nbody\n", "body"),
    ],
    ids=["plain", "empty-front", "broken-front", "list-front"],
)
async def test_readers_matter_without_frontmatter(text: str, body: str) -> None:
    assert read_matter(text, ["body"])["body"] == body


async def test_readers_json_paths_and_strays() -> None:
    tree = read_json(b'{"a": {"x": 1, "y": 2}, "b": 3, "c": {"d": 4}}')
    assert sorted(read_json(b'{"z": 1, "a": 2} // a comment\n')) == ["a", "z"]
    assert get_structured(tree, "a.x") == 1
    assert get_structured(tree, "a.z") is MISSING
    assert get_structured(tree, "b.q") is MISSING
    assert strays_structured(tree, ["a.x", "c"]) == ["a.y", "b"]
    assert read_json(b"[1]") == {}
