"""transpiler.origin — a line of a flat skill, traced back to the structured file and line it was rendered from.

The flat skill is its structured instance laid out again: every reference copied byte for byte,
and `SKILL.md` a generated head (frontmatter, title) followed by `instructions.md` whole. So the
trace is arithmetic, not a guess — the head is however many lines the flat file has beyond the
source — and it is held to a fixpoint: the traced line must read exactly as the flat one does.
A line in the head belongs to `skill.yaml` (line 0: the manifest, not a line of it); a line that
does not read back traces to nothing, and the caller keeps the flat place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

#: The flat entry file, and the structured file its body is.
ENTRY: Final[str] = "SKILL.md"
BODY: Final[str] = "instructions.md"
MANIFEST: Final[str] = "skill.yaml"


class SkillOrigin:
    """One skill's flat render against its structured source."""

    def __init__(self, source: Path, flat: Path) -> None:
        """`source` is `core/<facet>/skills/<id>`, `flat` the rendered `skills/<id>`."""
        self.source = source
        self.flat = flat

    ##### PRIVATE #####

    @staticmethod
    def _locate_lines(path: Path) -> list[str]:
        return path.read_text().splitlines() if path.is_file() else []

    ############################################################

    ##### PUBLIC #####

    def locate(self, path: str, line: int) -> tuple[str, int] | None:
        """The structured file (skill-relative) and line a flat line came from; None when it does not read back."""
        body = path == ENTRY
        flat, source = self._locate_lines(self.flat / path), self._locate_lines(self.source / (BODY if body else path))
        head = len(flat) - len(source) if body else 0
        traced = line - head
        found = 0 < traced <= len(source) and line <= len(flat) and source[traced - 1] == flat[line - 1]
        return (
            (MANIFEST, 0)
            if body and source and 0 < line <= head
            else (BODY if body else path, traced)
            if found
            else None
        )
