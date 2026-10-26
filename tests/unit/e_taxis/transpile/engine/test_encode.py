"""tests/unit/e_taxis/transpile/engine/encode: placements grouped per target, encoded by the format their template declares."""

import pytest

from e_taxis.transpile.engine.encode import encode_projection, match_target
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.models.placement import Placement

TARGETS = {
    "skills/{id}/SKILL.md": {"format": "md+fm"},
    "mcp-user": {"format": "registry"},
    "w/SOUL.md": {"format": "link", "to": "persona/SOUL.md"},
    "x.ini": {"format": "ini"},
}


@pytest.mark.parametrize(
    ("path", "kind"),
    [("skills/a/SKILL.md", "md+fm"), ("skills/a/references/r.md", "file"), ("mcp-user", "registry")],
    ids=["template", "undeclared-copy", "exact"],
)
async def test_encode_match_target(path: str, kind: str) -> None:
    assert match_target(path, TARGETS)["format"] == kind


async def test_encode_projection_splits_files_registry_and_links() -> None:
    placements = [
        Placement("skills/a/SKILL.md", "body", "b", "skill", 0),
        Placement("mcp-user", "exa", {"type": "http"}, "config", 9),
        Placement("w/SOUL.md", "", None, "persona", 0),
    ]
    projection = encode_projection("cc", "/out", {"targets": TARGETS}, placements)
    assert list(projection.files) == ["skills/a/SKILL.md"]
    assert projection.registry == {"mcp-user": {"exa": {"type": "http"}}}
    assert projection.links == {"w/SOUL.md": "persona/SOUL.md"}
    assert projection.placements["mcp-user"][0].origin == "config[9]"


async def test_encode_projection_refuses_a_format_without_encoder() -> None:
    with pytest.raises(RenderError, match="ini"):
        encode_projection("cc", "/out", {"targets": TARGETS}, [Placement("x.ini", "a", 1, "config", 0)])
