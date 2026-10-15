"""tests/unit/e_taxis/models/primitive: `~` resolves against the run's home, and `~/.claude` against Claude's own dir."""

from pathlib import Path

import pytest

from e_taxis.models.catalog import Target
from e_taxis.models.primitive import PrimitiveContext


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("~/.claude/settings.json", "/cfg/claude/settings.json"),
        ("~/.claude", "/cfg/claude"),
        ("~/.local/bin/bd", "/h/.local/bin/bd"),
        ("~", "/h"),
        ("/opt/x", "/opt/x"),
    ],
    ids=["claude-file", "claude-dir", "home-file", "home", "absolute"],
)
async def test_primitive_context_expand(raw: str, expected: str) -> None:
    ctx = PrimitiveContext(target=Target.CLAUDECODE, home=Path("/h"), claude=Path("/cfg/claude"))
    assert ctx.expand(raw) == Path(expected)
