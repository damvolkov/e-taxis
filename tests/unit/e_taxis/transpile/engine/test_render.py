"""tests/unit/e_taxis/transpile/engine/render: rows become placements with their provenance, in declaration order."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.engine.render import SpecRender
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.transforms.catalog import CATALOG

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.transpile.engine.context import RowContext
    from e_taxis.transpile.models.nous import NousTree


def _render(tree: NousTree, spec: Mapping[str, Any], ctx: RowContext) -> SpecRender:
    return SpecRender(
        spec,
        slots={**tree.persona["base"]["slots"], **tree.persona["tekton"]["slots"]},
        ctx=ctx,
        transforms=CATALOG["claudecode"],
        entities=dict(tree.entities),
        folders={
            "skill": "core/tekton/skills/{id}",
            "agent": "core/tekton/agents/{id}",
            "command": "core/tekton/commands/{id}",
            "workflow": "core/tekton/workflows/{id}",
            "config": "core/tekton/config",
        },
        blobs=tree.blobs,
    )


async def test_render_claudecode_places_every_section(nous_tree: NousTree, ctx: RowContext) -> None:
    placements = _render(nous_tree, nous_tree.specs["tekton/claudecode"], ctx).run()
    targets = {placement.target for placement in placements}
    assert {
        "CLAUDE.md",
        "skills/algo-py-core/SKILL.md",
        "agents/builder.md",
        "commands/ship.md",
        "settings.json",
        "mcp-user",
    } <= targets
    assert "skills/algo-py-core/references/lib.md" in targets
    assert "mcp/playwright.json" in targets
    first = next(placement for placement in placements if placement.target == "CLAUDE.md")
    assert (first.fragment, first.origin, first.sources) == ("h1", "persona[0]", ("name",))


async def test_render_each_fans_out_and_skips_none(nous_tree: NousTree, ctx: RowContext) -> None:
    placements = _render(nous_tree, nous_tree.specs["tekton/claudecode"], ctx).run()
    names = [placement.fragment for placement in placements if placement.target == "mcp-user"]
    assert "e-gnosis" in names
    assert len(names) == len(nous_tree.config["tekton"]["mcp"]["servers"])


async def test_render_required_empty_refuses(nous_tree: NousTree, ctx: RowContext) -> None:
    spec = {
        **nous_tree.specs["tekton/claudecode"],
        "map": {
            "config": {
                "kind": "config",
                "target": "settings.json",
                "rows": [{"from": "main.ghost", "to": "#x", "required": True}],
            }
        },
    }
    with pytest.raises(RenderError, match="required"):
        _render(nous_tree, spec, ctx).run()


async def test_render_unknown_via_refuses(nous_tree: NousTree, ctx: RowContext) -> None:
    spec = {
        **nous_tree.specs["tekton/claudecode"],
        "map": {
            "config": {
                "kind": "config",
                "target": "settings.json",
                "rows": [{"from": "main.user", "to": "#x", "via": "ghost"}],
            }
        },
    }
    with pytest.raises(RenderError, match="ghost"):
        _render(nous_tree, spec, ctx).run()


async def test_render_holes_bind_core_paths_and_constants(nous_tree: NousTree, ctx: RowContext) -> None:
    rows = [
        {"value": "{out}/w", "to": "#a.{main.user}"},
        {"from": "main.ghost", "to": "#b"},
        {"value": 1, "to": "#c.{nowhere}"},
    ]
    spec = {
        **nous_tree.specs["tekton/claudecode"],
        "map": {"config": {"kind": "config", "target": "settings.json", "rows": rows}},
    }
    placed = [(placement.fragment, placement.value) for placement in _render(nous_tree, spec, ctx).run()]
    assert placed == [("a.damien", "/out/w"), ("c.{nowhere}", 1)]


async def test_render_a_row_without_source_or_a_null_shape_places_nothing(nous_tree: NousTree, ctx: RowContext) -> None:
    rows = [{"to": "#a"}, {"value": 0, "to": "#b", "via": {"falsy": None}}, {"value": 1, "to": "#c"}]
    spec = {
        **nous_tree.specs["tekton/claudecode"],
        "map": {"config": {"kind": "config", "target": "settings.json", "rows": rows}},
    }
    assert [placement.fragment for placement in _render(nous_tree, spec, ctx).run()] == ["c"]
