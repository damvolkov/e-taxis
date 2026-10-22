"""transpiler.origin: a flat skill line traces to its structured file and line, or to nothing."""

from __future__ import annotations

from pathlib import Path

import pytest

from ops.transpiler.origin import SkillOrigin


@pytest.fixture
def origin(tmp_path: Path) -> SkillOrigin:
    source, flat = tmp_path / "core", tmp_path / "flat"
    (source / "references").mkdir(parents=True)
    (flat / "references").mkdir(parents=True)
    (source / "instructions.md").write_text("rule one\nrule two\n")
    (flat / "SKILL.md").write_text("---\nname: x\n---\n# x\nrule one\nrule two\n")
    (source / "references" / "a.md").write_text("alpha\nbeta\n")
    (flat / "references" / "a.md").write_text("alpha\nbeta\n")
    return SkillOrigin(source, flat)


@pytest.mark.parametrize(
    ("path", "line", "expected"),
    [
        ("SKILL.md", 6, ("instructions.md", 2)),
        ("SKILL.md", 2, ("skill.yaml", 0)),
        ("references/a.md", 2, ("references/a.md", 2)),
        ("references/a.md", 9, None),
        ("references/ghost.md", 1, None),
    ],
    ids=["body", "head", "reference", "past-the-end", "absent"],
)
async def test_origin_locate(origin: SkillOrigin, path: str, line: int, expected: tuple[str, int] | None) -> None:
    assert origin.locate(path, line) == expected


async def test_origin_locate_without_a_source_traces_nothing(tmp_path: Path, origin: SkillOrigin) -> None:
    assert SkillOrigin(tmp_path / "nowhere", origin.flat).locate("SKILL.md", 2) is None


async def test_origin_locate_refuses_a_line_that_does_not_read_back(origin: SkillOrigin) -> None:
    (origin.flat / "references" / "a.md").write_text("alpha\nedited\n")
    assert origin.locate("references/a.md", 2) is None
