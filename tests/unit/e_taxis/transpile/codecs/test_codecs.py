"""tests/unit/e_taxis/transpile/codecs: each encoder turns placements into the bytes its format prescribes."""

import msgspec
import pytest

from e_taxis.transpile.codecs.markdown import encode_markdown
from e_taxis.transpile.codecs.matter import encode_matter
from e_taxis.transpile.codecs.raw import encode_file, encode_text
from e_taxis.transpile.codecs.structured import encode_json
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.models.placement import Placement


def _at(fragment: str, value: object, glue: str = "\n\n") -> Placement:
    return Placement("t", fragment, value, "s", 0, (), glue)


async def test_codecs_markdown_typesets_blocks() -> None:
    placements = [
        _at("h1", "Demian"),
        _at("para", "lead\n"),
        _at("quote", "a\nb"),
        _at("Voice", "- one", "\n"),
        _at("Voice", "- two", "\n"),
        _at("Empty", "\n"),
        _at("Last", "end"),
    ]
    assert (
        encode_markdown("t", {}, placements)
        == b"# Demian\n\nlead\n\n> a\n> b\n\n## Voice\n\n- one\n- two\n\n## Last\n\nend"
    )


async def test_codecs_markdown_refuses_above_the_limit() -> None:
    with pytest.raises(RenderError, match="limit of 3"):
        encode_markdown("t", {"limit": 3}, [_at("para", "four")])


async def test_codecs_matter_assembles_frontmatter_title_preload_body() -> None:
    placements = [
        _at("fm.name", "x"),
        _at("fm.empty", []),
        _at("title", "x"),
        _at("preload", "Load first: a."),
        _at("body", "text\n\n"),
    ]
    assert encode_matter("t", {}, placements) == b"---\nname: x\n---\n\n# x\n\nLoad first: a.\n\ntext\n"


async def test_codecs_json_nests_dotted_fragments_in_order() -> None:
    data = encode_json("t", {}, [_at("$schema", "s"), _at("permissions.allow", ["a"]), _at("permissions.mode", "auto")])
    assert data.endswith(b"}\n")
    assert list(msgspec.json.decode(data)) == ["$schema", "permissions"]
    assert msgspec.json.decode(data)["permissions"] == {"allow": ["a"], "mode": "auto"}


async def test_codecs_raw_text_and_file() -> None:
    assert encode_text("t", {}, [_at("", "@a\n")]) == b"@a\n"
    assert encode_file("t", {}, [_at("", b"\x00\x01")]) == b"\x00\x01"
