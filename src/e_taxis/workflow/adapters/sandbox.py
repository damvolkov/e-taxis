"""adapters.sandbox: the only place an enhancement writes — a clone of the checkout at the run's base — and the git a
plane run needs around it.

The clone is `git clone --shared --no-checkout` then a detached checkout of the base: its own `.git`, objects shared,
never a worktree — a worktree points back at the real repository, and an agent run inside one resolves the real repo
as its project and writes there. `fingerprint` lets a node prove a session wrote nothing outside its clone; `diff`
cuts the patch a promotion applies, new files included; `apply` is that promotion, a three-way merge. A subject's
path may be a folder (an entity) or a file (a spec): `overlay` copies either, deletions included."""

import hashlib
import shutil
from typing import TYPE_CHECKING

import anyio

from e_taxis.workflow.models.error import CommandError

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
GIT: float = 120.0
ABSENT: str = "absent"


##### TYPES #####
class GitSandbox:
    """Satisfies SandboxPort over the `git` CLI."""

    __slots__ = ("_command",)

    def __init__(self, command: CommandPort) -> None:
        self._command = command

    ##### PRIVATE METHODS #####

    async def _common_git(self, repo: Path, *args: str) -> str:
        return await self._command.run("git", "-C", str(repo), *args, limit=GIT)

    @staticmethod
    def _fingerprint_hash(repo: Path, path: str) -> str:
        file = repo / path
        return hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else ABSENT

    @staticmethod
    def _overlay_copy(source: Path, target: Path) -> None:
        """`target` made byte-identical to `source`: a folder, a file, or nothing at all."""
        match target.is_dir():
            case True:
                shutil.rmtree(target)
            case _:
                target.unlink(missing_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        match (source.is_dir(), source.is_file()):
            case (True, _):
                shutil.copytree(source, target)
            case (_, True):
                shutil.copy2(source, target)
            case _:
                pass

    ############################################################

    ##### PUBLIC #####

    async def head(self, repo: Path) -> str:
        return (await self._common_git(repo, "rev-parse", "HEAD")).strip()

    async def dirty(self, repo: Path, *paths: str) -> tuple[str, ...]:
        """Paths that differ from HEAD, tracked or not."""
        raw = await self._common_git(repo, "status", "--porcelain", "--", *paths)
        return tuple(line[3:] for line in raw.splitlines() if line)

    async def created(self, repo: Path, *paths: str) -> tuple[str, ...]:
        """Paths that exist in the tree and not in git: what a session created."""
        return tuple((await self._common_git(repo, "ls-files", "--others", "--exclude-standard", "--", *paths)).split())

    async def open(self, repo: Path, path: Path, base: str) -> Path:
        """`repo` cloned into `path` at `base`; an existing clone (a resumed run) is reused."""
        match await anyio.Path(path / ".git").is_dir():
            case True:
                return path
            case _:
                await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
                await self._common_git(repo, "clone", "--quiet", "--shared", "--no-checkout", str(repo), str(path))
                await self._common_git(path, "checkout", "--quiet", "--detach", base)
                return path

    async def close(self, path: Path) -> None:
        """The clone deleted; the patches and renders beside it stay."""
        await anyio.to_thread.run_sync(lambda: shutil.rmtree(path, ignore_errors=True))

    async def fingerprint(self, repo: Path) -> tuple[str, dict[str, str]]:
        """(digest, dirty path → content hash): equal digests mean nothing was written."""
        status = await self._common_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
        paths = sorted(line[3:].split(" -> ")[-1] for line in status.splitlines() if line)
        hashes = {path: self._fingerprint_hash(repo, path) for path in paths}
        return hashlib.sha256(repr(sorted(hashes.items())).encode()).hexdigest(), hashes

    async def changed(self, repo: Path, base: str, rel: str) -> tuple[str, ...]:
        """Paths under `rel` the tree changed against `base`, untracked ones included."""
        tracked = await self._common_git(repo, "diff", "--name-only", base, "--", rel)
        untracked = await self._common_git(repo, "ls-files", "--others", "--exclude-standard", "--", rel)
        return tuple(sorted({*tracked.split(), *untracked.split()}))

    async def overlay(self, source: Path, target: Path, rel: str) -> None:
        """`target/rel` made byte-identical to `source/rel`, deletions included."""
        await anyio.to_thread.run_sync(self._overlay_copy, source / rel, target / rel)

    async def diff(self, sandbox: Path, base: str, rel: str) -> str:
        """The patch that turns `base` into the sandbox's `rel`, new files included, repo-relative."""
        await self._common_git(sandbox, "add", "--intent-to-add", "--all", "--", rel)
        return await self._common_git(sandbox, "diff", "--binary", base, "--", rel)

    async def apply(self, repo: Path, patch: Path, *, check: bool = False, reverse: bool = False) -> bool:
        """A run's patch applied to `repo` with a three-way merge; `check` only asks whether it would."""
        flags = (*(("--check",) if check else ("--3way",)), *(("--reverse",) if reverse else ()))
        try:
            await self._common_git(repo, "apply", *flags, str(patch))
        except CommandError:
            return False
        return True
