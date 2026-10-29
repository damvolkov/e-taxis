"""assess.inventory: what lives here today in the candidate's domain — read off the files, no model.

Five places are read: every table row of the corpus skills' `references/lib.md`, the parts of every `core/*/stack.yaml`,
the servers of `core/tekton/config/mcp.yaml`, the skills, agents and commands of each live transpiled tree (their
names and front-matter descriptions), and every past radar-tech report under the reports dir. A row is kept when its
text names one of the needles: the topic's keyword phrases and the candidate's name tokens (three characters or more),
matched whole-word, case-insensitive. Past assessments are kept whole: what was already judged is never filtered."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.assess import Candidate, Inventory, Row

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

##### DEFAULTS #####
LIBS: str = "core/*/skills/*/references/lib.md"
STACKS: str = "core/*/stack.yaml"
MCP: str = "core/tekton/config/mcp.yaml"
KINDS: Final[tuple[tuple[str, str], ...]] = (("skills", "*/SKILL.md"), ("agents", "*.md"), ("commands", "*.md"))
SEPARATOR: Final[re.Pattern[str]] = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
DESCRIPTION: Final[re.Pattern[str]] = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
TOKEN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")
SHORTEST: int = 3
ROLE: int = 160


##### TYPES #####
class AssessInventory:
    """Reads one e-nous checkout, the live trees and the past reports (`assessed` under `reports`)."""

    __slots__ = ("_nous", "_reports", "_trees")

    def __init__(self, nous: Path, *, trees: Sequence[Path], reports: Path) -> None:
        self._nous = nous
        self._trees = tuple(trees)
        self._reports = reports

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _common_glob(root: Path, pattern: str) -> list[Path]:
        return sorted([Path(path) async for path in anyio.Path(root).glob(pattern)])

    @staticmethod
    def _take_needles(candidate: Candidate, keywords: Iterable[str]) -> re.Pattern[str]:
        """The keyword phrases and the name tokens, longest first, as one whole-word pattern."""
        names = (candidate.name, candidate.repo.rpartition("/")[2], candidate.package)
        tokens = {token for name in names for token in TOKEN.split(name.lower()) if len(token) >= SHORTEST}
        needles = sorted(
            {*tokens, *(phrase.lower().strip() for phrase in keywords if phrase.strip())}, key=len, reverse=True
        )
        return re.compile(rf"(?<![a-z0-9])(?:{'|'.join(map(re.escape, needles))})(?![a-z0-9])", re.IGNORECASE)

    @staticmethod
    def _take_cells(line: str) -> list[str]:
        return [cell.strip().strip("*`").strip() for cell in line.strip().strip("|").split("|")]

    async def _take_libs(self) -> list[tuple[Row, str]]:
        """Every body row of every lib.md table: a `|` line that is no separator and heads no separator."""
        files = await self._common_glob(self._nous, LIBS)
        texts = [(path.relative_to(self._nous), (await anyio.Path(path).read_text()).splitlines()) for path in files]
        return [
            (Row(where=f"{rel}:{at + 1}", name=cells[0], role=" · ".join(cells[1:])[:ROLE]), line)
            for rel, lines in texts
            for at, (line, after) in enumerate(zip(lines, [*lines[1:], ""], strict=True))
            if line.lstrip().startswith("|") and not SEPARATOR.match(line) and not SEPARATOR.match(after)
            for cells in (self._take_cells(line),)
        ]

    async def _take_yaml(self, path: Path) -> dict[str, Any]:
        match await anyio.Path(path).is_file():
            case True:
                return eserde.loads(await anyio.Path(path).read_text(), format=eserde.Format.YAML) or {}
            case _:
                return {}

    async def _take_stacks(self) -> list[tuple[Row, str]]:
        files = await self._common_glob(self._nous, STACKS)
        parts = [(path.relative_to(self._nous), (await self._take_yaml(path)).get("parts") or {}) for path in files]
        return [
            (
                Row(where=str(rel), name=ident, role=f"{spec.get('kind', '')}: {spec.get('what', '')}"[:ROLE]),
                f"{ident} {spec}",
            )
            for rel, found in parts
            for ident, spec in found.items()
        ]

    async def _take_servers(self) -> list[tuple[Row, str]]:
        servers = (await self._take_yaml(self._nous / MCP)).get("servers") or {}
        return [
            (
                Row(
                    where=MCP,
                    name=ident,
                    role=f"mcp: {' '.join(map(str, spec.get('command') or [spec.get('url', '')]))}"[:ROLE],
                ),
                f"{ident} {spec}",
            )
            for ident, spec in servers.items()
        ]

    @staticmethod
    def _take_description(text: str) -> str:
        hit = DESCRIPTION.search(text)
        return hit.group(1).strip().strip("\"'") if hit else ""

    async def _take_tree(self, tree: Path) -> list[tuple[Row, str]]:
        """A live tree's skills, agents and commands: the id and the description its front matter declares."""
        files = [(kind, path) for kind, pattern in KINDS for path in await self._common_glob(tree / kind, pattern)]
        read = [(kind, path, await anyio.Path(path).read_text()) for kind, path in files]
        return [
            (Row(where=str(path), name=ident, role=f"{kind[:-1]}: {said}"[:ROLE]), f"{ident} {said}")
            for kind, path, text in read
            for ident in (path.parent.name if kind == "skills" else path.stem,)
            for said in (self._take_description(text),)
        ]

    async def _take_assessed(self) -> tuple[str, ...]:
        """Every past report, read loosely: a report an older model wrote still says what it judged."""
        files = await self._common_glob(self._reports, "*/radar/assess.json")
        reports = [(path, msgspec.json.decode(await anyio.Path(path).read_bytes())) for path in files]
        return tuple(
            f"{report.get('name', '?')}: {report.get('verdict', '?')} on {report.get('date', '?')} ({path})"
            for path, report in reports
        )

    ############################################################

    ##### PUBLIC #####

    async def take(self, candidate: Candidate, keywords: Iterable[str]) -> Inventory:
        """The rows that name the candidate's needles, and every past assessment."""
        needles = self._take_needles(candidate, keywords)
        trees = [row for tree in self._trees for row in await self._take_tree(tree)]
        rows = [*(await self._take_libs()), *(await self._take_stacks()), *(await self._take_servers()), *trees]
        return Inventory(
            rows=tuple(row for row, text in rows if needles.search(text)), assessed=await self._take_assessed()
        )
