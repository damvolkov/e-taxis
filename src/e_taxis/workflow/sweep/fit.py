"""sweep.fit: each finding marked have, considered or new — against what is written down, never from memory.

**The names.** A finding is known by its title and the repository names its links carry (GitHub, GitLab,
Codeberg: `owner/<name>`); its entities never decide — "NVIDIA" or "MCP" name what a thing touches, not the thing,
and would mark half the plane `have`. Each name is folded to lower-case words — every run of anything but letters
and digits is one space — and a name shorter than three characters says nothing and is dropped.

**The match.** A name occurs in a text when its words occur there as whole words, in order (`e-gnosis` matches
`e_gnosis` and `E Gnosis`, `otel` does not match `hotel`). The texts, read once:

- **have** — the corpus (`core/*/skills/*/references/lib.md`, `core/*/stack.yaml`, `core/tekton/config/mcp.yaml`)
  first, then the live trees the transpiler lands (settings and MCP JSON at their root, `mcp/`, the installed
  plugins, the skills' `lib.md`), never a session's history or a cache;
- **considered** — every `report.md` and `report.json` of a past soa-sweep or soa-assess run, this run's aside;
- **new** — none of them.

`incumbent` says which name matched, and where; the finding's entities that the same text also names are added
to it, as context — never as a match of their own. The first text that names the finding decides."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, Self
from urllib.parse import urlsplit

import anyio
import msgspec

from e_taxis.workflow.models.sweep import Finding, Findings, FindingStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

##### DEFAULTS #####
CORPUS: Final[tuple[str, ...]] = (
    "core/*/skills/*/references/lib.md",
    "core/*/stack.yaml",
    "core/tekton/config/mcp.yaml",
)
LIVE: Final[tuple[str, ...]] = (
    "*.json",
    "*.jsonc",
    "mcp/*",
    "plugins/installed_plugins.json",
    "plugins/*.js",
    "plugins/*.mjs",
    "skills/*/references/lib.md",
)
PAST: Final[tuple[str, ...]] = ("soa-sweep", "soa-assess")
REPORTS: Final[tuple[str, ...]] = ("report.md", "report.json")
FORGES: Final[frozenset[str]] = frozenset({"github.com", "gitlab.com", "codeberg.org"})
WORDS: Final[re.Pattern[str]] = re.compile(r"[^0-9a-z]+")
SHORT: int = 3


##### TYPES #####
class SweepFit:
    """The texts that know a name, by status, each under where it was read."""

    __slots__ = ("_texts",)

    def __init__(self, texts: Iterable[tuple[FindingStatus, str, str]]) -> None:
        self._texts = tuple((status, where, f" {self._common_fold(text)} ") for status, where, text in texts)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_fold(text: str) -> str:
        return WORDS.sub(" ", text.casefold()).strip()

    @staticmethod
    async def _load_read(paths: Iterable[Path], root: Path | None) -> list[tuple[str, str]]:
        """(where, text) per file: relative to `root` when given, the full path otherwise."""
        files = sorted({path for path in paths if await anyio.Path(path).is_file()})
        return [
            (str(path.relative_to(root)) if root else str(path), await anyio.Path(path).read_text(errors="replace"))
            for path in files
        ]

    @staticmethod
    async def _load_glob(root: Path, patterns: Iterable[str], *, deep: bool = False) -> list[Path]:
        """What the patterns match under `root` — at any depth when `deep`."""
        walk = anyio.Path(root).rglob if deep else anyio.Path(root).glob
        return [Path(found) for pattern in patterns async for found in walk(pattern)]

    @classmethod
    def _common_names(cls, names: Iterable[str]) -> tuple[str, ...]:
        folded = (cls._common_fold(name) for name in names)
        return tuple(dict.fromkeys(name for name in folded if len(name) >= SHORT))

    @classmethod
    def _fit_names(cls, finding: Finding) -> tuple[str, ...]:
        repos = (
            parts[2]
            for link in finding.links
            if urlsplit(link).netloc.removeprefix("www.") in FORGES and len(parts := urlsplit(link).path.split("/")) > 2  # noqa: PLR2004 — "", owner, name
        )
        return cls._common_names((finding.title, *repos))

    def _fit_one(self, finding: Finding) -> Finding:
        names = self._fit_names(finding)
        found = (
            (status, where, text, name) for status, where, text in self._texts for name in names if f" {name} " in text
        )
        match next(found, None):
            case (status, where, text, name):
                also = [entity for entity in self._common_names(finding.entities) if f" {entity} " in text]
                said = f"{name} (+ {', '.join(also)})" if also else name
                return msgspec.structs.replace(finding, status=status, incumbent=f"{said} — {where}")
            case _:
                return msgspec.structs.replace(finding, status=FindingStatus.NEW, incumbent="")

    ############################################################

    ##### PUBLIC #####

    @classmethod
    async def load(cls, nous: Path, live: Iterable[Path], reports: Path, rundir: Path) -> Self:
        """Read the corpus of `nous`, the `live` trees, and the past runs under `reports` but `rundir`."""
        corpus = await cls._load_read(await cls._load_glob(nous, CORPUS), nous)
        trees = [found for root in live for found in await cls._load_read(await cls._load_glob(root, LIVE), None)]
        runs = [run for kind in PAST for run in await cls._load_glob(reports / "workflows" / kind, ("*",))]
        past = [
            found
            for run in runs
            if run != rundir
            for found in await cls._load_read(await cls._load_glob(run, REPORTS, deep=True), None)
        ]
        return cls(
            (
                *((FindingStatus.HAVE, where, text) for where, text in (*corpus, *trees)),
                *((FindingStatus.CONSIDERED, where, text) for where, text in past),
            )
        )

    def fit(self, findings: Findings) -> Findings:
        return msgspec.structs.replace(
            findings, findings=tuple(self._fit_one(finding) for finding in findings.findings)
        )
