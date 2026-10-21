"""tests ops.repo: the deterministic git reads against real file-local remotes.

Origins are built with plain git plumbing in temp trees — no network, no mocks: what `taxis repo`
answers is what the remote really holds. A tag and a branch sharing a name pins the precedence; a
40-hex ref passing through unresolved pins the address-by-commit property."""

import io
import subprocess
import tarfile
from typing import TYPE_CHECKING

import anyio
import pytest

from e_taxis.harness.models.error import RepoError
from e_taxis.ops import repo

if TYPE_CHECKING:
    from pathlib import Path


async def _git(*args: str, cwd: Path) -> str:
    """One git call on the test's own temp tree; fixed argv, nothing here is input."""
    done = await anyio.run_process(("git", *args), cwd=cwd, check=False)
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode().strip()


COMMIT: tuple[str, ...] = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false")


@pytest.fixture
async def origin(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A committed repo: two releases, `v1` and `dual` tags, and `dual` also as a branch on the later one."""
    bare = tmp_path / "origin"
    await _git("init", "-q", "-b", "main", str(bare), cwd=tmp_path)
    (bare / "systems" / "core").mkdir(parents=True)
    (bare / "systems" / "core" / "one.txt").write_text("one\n")
    await _git("add", "-A", cwd=bare)
    await _git(*COMMIT, "commit", "-qm", "one", cwd=bare)
    shas = {"one": await _git("rev-parse", "HEAD", cwd=bare)}
    await _git("tag", "v1", cwd=bare)
    await _git("tag", "dual", cwd=bare)
    (bare / "systems" / "core" / "two.txt").write_text("two\n")
    await _git("add", "-A", cwd=bare)
    await _git(*COMMIT, "commit", "-qm", "two", cwd=bare)
    shas["two"] = await _git("rev-parse", "HEAD", cwd=bare)
    await _git("branch", "dual", cwd=bare)
    return bare, shas


##### RESOLVE #####


async def test_repo_resolve_tag_and_branch(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """A tag resolves to the commit it names; `main` follows the branch head."""
    bare, shas = origin
    cache = tmp_path / "cache"
    assert await repo._repo_sha(str(bare), "v1", await repo._repo_ensure(str(bare), cache)) == shas["one"]
    assert await repo._repo_sha(str(bare), "main", await repo._repo_ensure(str(bare), cache)) == shas["two"]


async def test_repo_resolve_prefers_tag_over_branch(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """`dual` is both a tag and a branch: the tag wins — the precedence the module promises."""
    bare, shas = origin
    cache = tmp_path / "cache"
    assert await repo._repo_sha(str(bare), "dual", await repo._repo_ensure(str(bare), cache)) == shas["one"]


async def test_repo_resolve_full_ref_exact(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """A fully qualified ref is no name to arbitrate: exact beats the precedence."""
    bare, shas = origin
    cache = tmp_path / "cache"
    assert await repo._repo_sha(str(bare), "refs/heads/dual", await repo._repo_ensure(str(bare), cache)) == shas["two"]


async def test_repo_resolve_sha_passes_through(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """A 40-hex commit needs no remote: the address is the answer, the bare untouched."""
    bare, shas = origin
    assert await repo._repo_sha(str(bare), shas["two"], tmp_path / "untouched") == shas["two"]
    assert not (tmp_path / "untouched").exists()


async def test_repo_resolve_unknown_ref(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """A name neither tag nor branch carries is refused, naming the remote and the ref."""
    bare, _ = origin
    cache = await repo._repo_ensure(str(bare), tmp_path / "cache")
    with pytest.raises(RepoError, match=r"nope.*no tag or branch"):
        await repo._repo_sha(str(bare), "nope", cache)


async def test_repo_ensure_fetches_on_second_visit(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """The first call clones the bare, the second fetches it: one cache per url, and a run sees what moved."""
    bare, shas = origin
    cache = tmp_path / "cache"
    first = await repo._repo_ensure(str(bare), cache)
    assert first == await repo._repo_ensure(str(bare), cache)
    assert first.is_dir()
    await _git(*COMMIT, "commit", "-q", "--allow-empty", "-m", "three", cwd=bare)
    moved = await _git("rev-parse", "main", cwd=bare)
    assert moved != shas["two"]
    _, sha = await repo._repo_open(str(bare), "main", cache)
    assert sha == moved


##### BROWSE AND UNPACK #####


async def test_repo_tree_lists_at_ref(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """The tree at the tag holds only what existed then; at main, both files."""
    bare, _ = origin
    cache = tmp_path / "cache"
    tree, tag = await repo._repo_open(str(bare), "v1", cache)
    assert await repo._repo_tree(tree, tag, "systems") == ("systems/core/one.txt",)
    _, head = await repo._repo_open(str(bare), "main", cache)
    assert await repo._repo_tree(tree, head, ".") == ("systems/core/one.txt", "systems/core/two.txt")


async def test_repo_tree_empty_path_refused(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """A path that names no file is a wrong name, not an empty tree: refused."""
    bare, _ = origin
    cache = tmp_path / "cache"
    tree, sha = await repo._repo_open(str(bare), "main", cache)
    with pytest.raises(RepoError, match="nope"):
        await repo._repo_tree(tree, sha, "nope")


async def test_repo_extract_lands_the_layout(origin: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    """Unpacking `systems` at the tag keeps the commit's layout under dest."""
    bare, _ = origin
    dest = tmp_path / "out"
    tree, sha = await repo._repo_open(str(bare), "v1", tmp_path / "cache")
    await repo._repo_extract(tree, sha, "systems", dest)
    assert (dest / "systems" / "core" / "one.txt").read_text() == "one\n"
    assert not (dest / "systems" / "core" / "two.txt").exists()


async def test_repo_extract_refuses_link_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tar is read with the `data` filter: a symlink out of dest is refused, never followed."""
    blob = io.BytesIO()
    with tarfile.open(fileobj=blob, mode="w") as archive:
        link = tarfile.TarInfo("escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../escaped"
        archive.addfile(link)

    async def fake_git(*args: str, cwd: Path | None = None) -> bytes:
        assert args[:2] == ("archive", "--format=tar")
        return blob.getvalue()

    monkeypatch.setattr(repo, "_git", fake_git)
    dest = tmp_path / "dest"
    with pytest.raises(Exception):  # noqa: B017, PT011 — the tar filter's own error class, message about the link
        await repo._repo_extract(tmp_path / "bare", "0" * 40, "any", dest)
    assert not (dest / "escape").exists()


##### COMMAND SURFACE #####


async def test_repo_commands_print(
    origin: tuple[Path, dict[str, str]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The three cards run end to end: the commit, the names and the destination reach the console."""
    bare, shas = origin
    cache = tmp_path / "cache"
    await repo.resolve(str(bare), "v1", cache=cache)
    await repo.tree(str(bare), "v1", "systems", cache=cache)
    dest = tmp_path / "landed"
    await repo.extract(str(bare), "main", "systems", dest=dest, cache=cache)
    printed = capsys.readouterr().out
    assert shas["one"] in printed
    assert "systems/core/one.txt" in printed
    assert str(dest) in printed


async def test_repo_ensure_refuses_unreachable_url(tmp_path: Path) -> None:
    """A remote that will not answer is refused with git's own reason."""
    with pytest.raises(RepoError, match="git clone"):
        await repo._repo_ensure(str(tmp_path / "nowhere"), tmp_path / "cache")


async def test_repo_git_failure_without_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git failure that says nothing: the refusal still names the command — the silent half of the message."""

    async def silent(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=(), returncode=1, stdout=b"", stderr=b"")

    monkeypatch.setattr(repo.anyio, "run_process", silent)
    with pytest.raises(RepoError, match="no reason given"):
        await repo._git("status", cwd=tmp_path)
