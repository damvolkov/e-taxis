"""distill.scope: what a reverse-distill run reads of the project — its branches, their base, their commits and files.

`guard` fixes the scope (the project, the branches, the base they grew from) and ends the run with "nothing to do"
(exit 3) when no branch carries a commit past its base — every later step is skipped, zero tokens. `intake` lists
those commits and the files they touched, weighed and classed as code, structured data or docs. Both read git only:
committed work, never the working tree."""

from pathlib import Path
from typing import TYPE_CHECKING, Final

import anyio

from e_taxis.workflow.models.distill import CommitRow, FileKind, FileRow, Manifest, Scope
from e_taxis.workflow.models.error import CommandError, NothingError

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
STRUCTURED: Final[frozenset[str]] = frozenset({".yaml", ".yml", ".toml", ".json", ".jsonc", ".ini", ".cfg", ".env"})
DOCS: Final[frozenset[str]] = frozenset({".md", ".rst", ".txt"})
### `str.strip()` counts both separators as whitespace: a record is stripped of newlines only, or a commit with an
### empty body loses its last field and vanishes.
UNIT: str = "\x1f"
RECORD: str = "\x1e"
FIELDS: int = 3
GIT: float = 60.0


##### TYPES #####
class DistillScope:
    """git, read-only, in the project."""

    __slots__ = ("_command",)

    def __init__(self, command: CommandPort) -> None:
        self._command = command

    ##### PRIVATE METHODS #####

    async def _common_git(self, project: Path, *args: str) -> str:
        return await self._command.run("git", "-C", str(project), *args, limit=GIT)

    @staticmethod
    def _intake_kind(path: str) -> FileKind:
        suffix = Path(path).suffix.lower()
        return FileKind.STRUCTURED if suffix in STRUCTURED else FileKind.DOCS if suffix in DOCS else FileKind.CODE

    @staticmethod
    def _intake_row(line: str) -> FileRow | None:
        match line.split("\t"):
            case [added, removed, path]:
                return FileRow(
                    path=path,
                    kind=DistillScope._intake_kind(path),
                    added=int(added) if added.isdigit() else 0,
                    removed=int(removed) if removed.isdigit() else 0,
                )
            case _:
                return None

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def graph_name(project: Path) -> str:
        """The name codebase-memory gives a repository: its absolute (resolved) path, slashes as dashes."""
        return "-".join(project.parts[1:])

    async def guard(self, project: Path, branches: tuple[str, ...], since: str, work: str) -> Scope:
        """The run's scope; `NothingError` when no branch has a commit past the base."""
        project = Path(await (await anyio.Path(project).expanduser()).resolve())
        try:
            current = (await self._common_git(project, "rev-parse", "--abbrev-ref", "HEAD")).strip()
        except CommandError as failed:
            msg = f"{project} is not a git repository"
            raise NothingError(msg) from failed
        heads = branches or (current,)
        base = (
            await self._common_git(project, "rev-parse", "--verify", f"{since}^{{commit}}")
            if since
            else await self._common_git(project, "merge-base", "main", heads[0])
        ).strip()
        counts = [
            int((await self._common_git(project, "rev-list", "--count", f"{base}..{head}")).strip()) for head in heads
        ]
        match any(counts):
            case False:
                msg = f"no commit past {base[:12]} on {', '.join(heads)}"
                raise NothingError(msg)
            case _:
                return Scope(project=str(project), graph=self.graph_name(project), branches=heads, base=base, work=work)

    async def changed(self, scope: Scope) -> tuple[str, ...]:
        """Every file the branches changed in the run's range (`base...head`, committed work only), once, sorted."""
        project = Path(scope.project)
        names = [
            await self._common_git(project, "diff", "--name-only", f"{scope.base}...{head}") for head in scope.branches
        ]
        return tuple(sorted({path for listing in names for path in listing.splitlines() if path}))

    async def intake(self, scope: Scope) -> Manifest:
        """Every commit since the base on every branch, and every file they touched, once each."""
        project = Path(scope.project)
        logs = [
            await self._common_git(project, "log", f"--format=%H{UNIT}%s{UNIT}%b{RECORD}", f"{scope.base}..{head}")
            for head in scope.branches
        ]
        commits = {
            fields[0]: CommitRow(sha=fields[0], subject=fields[1], body=fields[2].strip())
            for log in logs
            for record in log.split(RECORD)
            if len(fields := record.strip("\n").split(UNIT)) == FIELDS
        }
        stats = [
            await self._common_git(project, "diff", "--numstat", f"{scope.base}...{head}") for head in scope.branches
        ]
        files = {row.path: row for stat in stats for line in stat.splitlines() if (row := self._intake_row(line))}
        return Manifest(
            scope=scope, commits=tuple(commits.values()), files=tuple(sorted(files.values(), key=lambda f: f.path))
        )
