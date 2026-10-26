"""tests/unit/e_taxis/transpile/engine/plan_nomos: tables wait, shared lists merge, foreign keys and env lines stay."""

import tomllib

from e_taxis.transpile.engine.plan import dormant_plan, fragments_plan, items_plan, land_plan, ours_plan, target_plan
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.models.report import ReportKind

FOREIGN = [
    {"kind": "key", "at": "*", "why": "the app's"},
    {"kind": "table", "at": "channels", "why": "created by the app"},
    {"kind": "items", "at": "servers", "by": "name", "why": "the app installs some"},
    {"kind": "items", "at": "sources", "by": "id", "ours": {"kind": "folder"}, "why": "other kinds are the app's"},
]


def _at(fragment: str, value: object) -> Placement:
    return Placement("c.toml", fragment, value, "config", 0, ("x",))


ROWS = [
    _at("model", "m"),
    _at("channels.id", 1),
    _at("servers", [{"name": "a", "enabled": True}]),
    _at("sources", [{"id": "s", "kind": "folder"}]),
]


async def test_plan_nomos_export_drops_dormant_tables() -> None:
    assert [p.fragment for p in dormant_plan(ROWS, None, FOREIGN)] == ["model", "servers", "sources"]
    assert [p.fragment for p in dormant_plan(ROWS, {"channels": {}}, FOREIGN)] == [p.fragment for p in ROWS]


async def test_plan_nomos_items_merge_and_compare() -> None:
    live = [{"name": "a", "enabled": False, "extra": 1}, {"name": "theirs"}]
    assert items_plan([{"name": "a", "enabled": True}], live, FOREIGN[2]) == [
        {"name": "a", "enabled": True, "extra": 1},
        {"name": "theirs"},
    ]
    folders = [{"id": "s", "kind": "folder"}, {"id": "old", "kind": "folder"}, {"id": "gh", "kind": "composio"}]
    assert items_plan([{"id": "s", "kind": "folder"}], folders, FOREIGN[3]) == [
        {"id": "s", "kind": "folder"},
        {"id": "gh", "kind": "composio"},
    ]
    assert ours_plan([{"id": "s", "kind": "folder"}], folders, FOREIGN[3]) == [
        {"id": "s", "kind": "folder"},
        {"id": "old", "kind": "folder"},
    ]
    assert items_plan("x", "y", FOREIGN[2]) == "x"
    assert ours_plan("x", "y", FOREIGN[2]) == "y"


async def test_plan_nomos_land_toml_keeps_the_apps_and_waits_for_tables() -> None:
    live = b'model = "old"\nschema_version = 13\n[[servers]]\nname = "theirs"\n'
    landed = tomllib.loads(land_plan("toml", b"", live, FOREIGN, ROWS).decode())
    assert landed["model"] == "m"
    assert landed["schema_version"] == 13
    assert "channels" not in landed
    assert [server["name"] for server in landed["servers"]] == ["a", "theirs"]
    exported = tomllib.loads(land_plan("toml", b"", None, FOREIGN, ROWS).decode())
    assert "channels" not in exported


async def test_plan_nomos_fragments_and_dormant_findings() -> None:
    live = b'model = "m"\nschema_version = 13\n[[servers]]\nname = "a"\nenabled = true\nmore = 1\n[[sources]]\nid = "s"\nkind = "folder"\n'
    rendered, found = fragments_plan("toml", ROWS, live, FOREIGN)
    assert "channels.id" not in rendered
    assert found["servers"] == [{"name": "a", "enabled": True}]
    findings = list(target_plan("oh", "c.toml", {"format": "toml", "foreign": FOREIGN}, ROWS, landed=b"x", live=live))
    assert [(f.kind, f.path) for f in findings] == [
        (ReportKind.DORMANT, "c.toml#channels.id"),
        (ReportKind.DRIFT, "c.toml"),
    ]


async def test_plan_nomos_env_keeps_foreign_lines_and_yaml_compares() -> None:
    env = [Placement(".env", "A", "1", "config", 0)]
    foreign = [{"kind": "key", "at": "*", "why": "secrets"}]
    assert land_plan("env", b"A=1\n", b"A=0\nSECRET=s\n# note\n", foreign, env) == b"A=1\nSECRET=s\n# note\n"
    assert fragments_plan("env", env, b"A=0\nSECRET=s\n", foreign) == ({"A": "1"}, {"A": "0"})
    rendered, found = fragments_plan("yaml", [Placement("c.yaml", "a.b", 1, "config", 0)], b"a:\n  b: 2\nz: 1\n", [])
    assert (rendered, found) == ({"a.b": 1}, {"a.b": 2, "z": 1})
