"""tests/unit/e_taxis/transpile/engine/plan: each fragment held to the live tree; foreign parts kept; strays named."""

import msgspec

from e_taxis.transpile.engine.plan import governed_plan, land_plan, owned_plan, registry_plan, target_plan
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.models.report import ReportKind

MARKER = [{"kind": "marker", "start": "<!-- a:(?P<b>[a-z]+):start -->", "end": "<!-- a:(?P=b):end -->"}]
JSON_KEYS = [{"kind": "key", "at": "keep*"}]


def _at(fragment: str, value: object, row: int = 0) -> Placement:
    return Placement("f", fragment, value, "config", row, ("main.user",))


async def test_plan_owned_cuts_the_foreign_regions() -> None:
    text = "lead\n\n<!-- a:g:start -->\nmine\n<!-- a:g:end -->\n\ntail"
    assert owned_plan(text, MARKER) == "lead\n\ntail"
    assert owned_plan("plain", []) == "plain"


async def test_plan_land_carries_foreign_parts() -> None:
    live_md = b"old\n\n<!-- a:g:start -->\nlearned\n<!-- a:g:end -->"
    assert land_plan("md", b"new", live_md, MARKER, []) == b"new\n\n<!-- a:g:start -->\nlearned\n<!-- a:g:end -->"
    assert (
        land_plan("md", b"new", b"x\n\xc2\xa7\nentry", [{"kind": "marker", "start": "\n§\n", "end": "\\Z"}], [])
        == b"new\n\xc2\xa7\nentry"
    )
    landed = land_plan("json", b"{}", b'{"keep_me": 1, "drop": 2, "a": 0}', JSON_KEYS, [_at("a", 5)])
    assert msgspec.json.decode(landed) == {"a": 5, "keep_me": 1}
    assert land_plan("json", b"R", None, JSON_KEYS, []) == b"R"
    assert land_plan("text", b"R", b"L", JSON_KEYS, []) == b"R"
    assert land_plan("md", b"R", b"L", [], []) == b"R"


async def test_plan_target_missing_settled_and_fragments() -> None:
    placements = [_at("a", 1), _at("b.c", 2, 1)]
    target = {"format": "json"}
    assert [f.kind for f in target_plan("cc", "s.json", target, placements, landed=b"{}", live=None)] == [
        ReportKind.MISSING
    ]
    assert list(target_plan("cc", "s.json", target, placements, landed=b"X", live=b"X")) == []
    found = list(target_plan("cc", "s.json", target, placements, landed=b"{}", live=b'{"a": 1, "b": {"c": 3}, "z": 0}'))
    assert [(f.kind, f.path, f.where) for f in found] == [
        (ReportKind.DRIFT, "s.json#b.c", "config[1]"),
        (ReportKind.STALE, "s.json#z", "—"),
    ]
    assert found[0].sources == ("main.user",)
    reordered = list(
        target_plan("cc", "s.json", target, placements, landed=b'{"a":1,"b":{"c":2}}', live=b'{"b":{"c":2},"a":1}')
    )
    assert [(f.kind, f.detail) for f in reordered] == [(ReportKind.DRIFT, "same fragments, other bytes")]


async def test_plan_target_markdown_matter_and_file() -> None:
    md = [_at("h1", "T"), _at("Voice", "v")]
    found = list(
        target_plan(
            "cc",
            "C.md",
            {"format": "md"},
            md,
            landed=b"# T\n\n## Voice\n\nv",
            live=b"# T\n\n## Voice\n\nw\n\n## Mine\n\nm",
        )
    )
    assert {(f.kind, f.path) for f in found} == {(ReportKind.DRIFT, "C.md#Voice"), (ReportKind.STALE, "C.md#Mine")}
    fm = [_at("fm.name", "x"), _at("body", "b")]
    found = list(
        target_plan(
            "cc", "a.md", {"format": "md+fm"}, fm, landed=b"---\nname: x\n---\n\nb\n", live=b"---\nname: y\n---\n\nb\n"
        )
    )
    assert [f.path for f in found] == ["a.md#fm.name"]
    blob = [Placement("h", "", b"new", "config", 9)]
    assert [f.path for f in target_plan("cc", "h", {"format": "file"}, blob, landed=b"new", live=b"old")] == ["h"]


async def test_plan_governed_strays_skip_foreign() -> None:
    found = governed_plan(
        "cc",
        ["skills"],
        ["skills/synced", "skills/.trash"],
        ["skills/a/SKILL.md"],
        ["skills/a/SKILL.md", "skills/b/SKILL.md", "skills/synced/x.md", "skills/.trash/1/y", "rules/x"],
    )
    assert [f.path for f in found] == ["skills/b/SKILL.md"]


async def test_plan_registry_missing_drift_stale() -> None:
    placements = [
        Placement("mcp-user", "a", {"u": 1}, "config", 13, ("mcp.servers",)),
        Placement("mcp-user", "b", {"u": 2}, "config", 13),
    ]
    found = list(registry_plan("cc", "mcp-user", placements, {"b": {"u": 0}, "c": {}}))
    assert [(f.kind, f.path) for f in found] == [
        (ReportKind.MISSING, "mcp-user#a"),
        (ReportKind.DRIFT, "mcp-user#b"),
        (ReportKind.STALE, "mcp-user#c"),
    ]
