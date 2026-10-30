"""ops/repo: `taxis repo` — deterministic git reads on a remote, from the bare: a ref resolves to a commit,
a tree is listed, a path is unpacked. No working checkout is ever made.

One bare clone per url lives under the cache, created by `clone` and kept current by a refspec-carrying
`fetch`, so a run touches the network once. Content is then addressed by the resolved commit: listing
and unpacking read that commit alone, and a branch moving mid-run cannot split one install across two
versions. The url may also be a `file://` path or a plain directory: the offline dev box, CI's checkout
and the public remote are one code path. A ref name resolves by precedence — exact ref, tag, branch —
so a tag wins its same-named branch, and a full 40-hex commit passes through unresolved."""

import hashlib
import io
import re
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import anyio
from rich.console import Console

from e_taxis.harness.models.error import RepoError

if TYPE_CHECKING:
    import subprocess

##### DEFAULTS #####
CACHE: Final[Path] = Path.home() / ".cache" / "e-taxis" / "remotes"
SHA: Final = re.compile(r"^[0-9a-f]{40}$")
### a bare clone tracks HEAD alone: fetch must name the refspecs to carry every branch and tag.
REFSPECS: Final[tuple[str, ...]] = ("+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*")
CANDIDATES: Final[tuple[str, ...]] = ("{}", "refs/tags/{}", "refs/heads/{}")


##### COMMAND #####


async def resolve(url: str, ref: str, *, cache: Path = CACHE) -> None:
    """Print the commit a ref names on the remote.

    Args:
        url: the git remote: an https or ssh repository, or a local path for offline work.
        ref: a branch, a tag or a full commit to resolve.
        cache: root of the bare clones.
    """
    bare = await _repo_ensure(url, cache)
    Console(soft_wrap=True).print(await _repo_sha(url, ref, bare))


async def tree(url: str, ref: str, path: str = ".", *, cache: Path = CACHE) -> None:
    """Print every file under path at the ref: what the remote's repo holds, read without a working tree.

    Args:
        url: the git remote.
        ref: a branch, a tag or a full commit.
        path: the directory to list, whole repo by default.
        cache: root of the bare clones.
    """
    bare, sha = await _repo_open(url, ref, cache)
    _ = [Console(soft_wrap=True).print(name) for name in await _repo_tree(bare, sha, path)]


async def extract(url: str, ref: str, path: str, *, dest: Path, cache: Path = CACHE) -> None:
    """Unpack path at the ref under dest, its layout as the commit holds it; print dest.

    Args:
        url: the git remote.
        ref: a branch, a tag or a full commit.
        path: the directory to unpack, e.g. projects/python/common.
        dest: the directory to land it in.
        cache: root of the bare clones.
    """
    bare, sha = await _repo_open(url, ref, cache)
    await _repo_extract(bare, sha, path, dest)
    Console(soft_wrap=True).print(dest)


##### PRIVATE #####


async def _git(*args: str, cwd: Path | None = None) -> bytes:
    """One git call, its stdout captured; a non-zero exit is named with the command and git's own reason."""
    done = await anyio.run_process(("git", *args), cwd=cwd, check=False)
    return done.stdout if not done.returncode else _git_refused(done, args)


def _git_refused(done: subprocess.CompletedProcess[bytes], args: tuple[str, ...]) -> bytes:
    """The refusal names the command and git's own reason; when git says nothing, it is said for it."""
    msg = f"git {' '.join(args)}: exit {done.returncode} · {done.stderr.decode().strip() or 'no reason given'}"
    raise RepoError(msg)


async def _repo_open(url: str, ref: str, cache: Path) -> tuple[Path, str]:
    """The bare cache of a remote and the commit a ref names, together: one ensure, one fetch per run."""
    bare = await _repo_ensure(url, cache)
    return bare, await _repo_sha(url, ref, bare)


async def _repo_ensure(url: str, cache: Path) -> Path:
    """The remote's bare clone: created once, kept current by a prune-fetch over every head and tag."""
    path = anyio.Path(cache / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.git")
    await path.parent.mkdir(parents=True, exist_ok=True)
    repo = Path(str(path))
    await (
        _git("clone", "--bare", url, str(repo))
        if await path.is_dir() is False
        else _git("fetch", "--prune", "origin", *REFSPECS, cwd=repo)
    )
    return repo


async def _repo_sha(url: str, ref: str, repo: Path) -> str:
    """The commit a ref names against an already-fetched bare: full shas pass through, names resolve by precedence."""
    match ref:
        case sha if SHA.fullmatch(sha):
            return sha
        case name:
            wanted = tuple(pattern.format(name) for pattern in CANDIDATES)
            listed = {
                line.split("\t", 1)[1]: line.split("\t", 1)[0]
                for line in (await _git("ls-remote", str(repo), *wanted)).decode().splitlines()
            }
            hits = [found for candidate in wanted if (found := listed.get(candidate))]
            return hits[0] if hits else _sha_missing(url, name)


def _sha_missing(url: str, name: str) -> str:
    """A wanted name that neither tag nor branch carries: refused, never guessed."""
    msg = f"{url}: {name} resolves to no tag or branch on the remote"
    raise RepoError(msg)


async def _repo_tree(repo: Path, sha: str, path: str) -> tuple[str, ...]:
    """Every file path under `path` at the commit; a name listing nothing is a wrong name, not an empty tree."""
    names = tuple((await _git("ls-tree", "-r", "--name-only", sha, "--", path, cwd=repo)).decode().splitlines())
    match names:
        case found if found:
            return found
        case _:
            msg = f"{path}: no files at {sha[:8]} in {repo.name}"
            raise RepoError(msg)


async def _repo_extract(repo: Path, sha: str, path: str, dest: Path) -> None:
    """The commit's `path` as the tar git archives it, landed under dest: `data` filter — no link escapes."""
    blob = await _git("archive", "--format=tar", sha, "--", path, cwd=repo)
    await anyio.Path(dest).mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        archive.extractall(dest, filter="data")
