"""transpiler.history.store — the corpus history, kept by git, one directory away from the corpus.

The harness lives in a directory other programs write into: runtimes drop sessions
there, plugins regenerate trees, the transpile overwrites files wholesale. Versioning
it needs three properties and git already has all three — content addressing, exact
pointers, and a restore that is a file operation rather than a merge.

Two decisions make it fit this particular tree:

**The git dir lives apart** (`~/.local/state/e-nous/…`), so the versioned directory
never contains a `.git` for a plugin to index, a runtime to clean, or an agent to
wander into. This is the bare-dotfiles arrangement, and it also means an accidental
`rm -rf` of the config dir does not take the history with it.

**Every snapshot is a parentless commit** under its own ref. Blobs are content
addressed, so nothing is duplicated between snapshots; but because no snapshot is
an ancestor of another, dropping a ref genuinely releases its unique objects at the
next `gc`. A linear history would make retention impossible without rewriting it.

Scope is declared once, as git's own `info/exclude`: inside the git dir, never in the
tree, so the corpus directory carries no file of ours.

**The specs a point was rendered with ride beside it.** A spec change that moves no
rendered byte (a metadata date, a key the render never meets) is invisible to a diff of
the tree, yet it changed how the tree is made. `seal` records the `specs/` tree an
export was produced with under `refs/specs/<point>`, in this same git dir, through a
private index: nothing is written to the repo or to the harness. `specs` reads back
what moved since.

Mounted through `op transpiler init|apply|log|restore|prune`; usable alone:
    Store(Path("~/.config/opencode")).snapshot("manual", note="before I touch it")

The default git dir sits under `settings.global_.state_dir` (`~/.local/state/e-nous/`), the
same home as plugin and runtime metadata — never inside the tree it versions.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

from ops.core.settings import settings
from ops.models.history import FileChange, Kind, Reason, Retention, Snapshot

#: Where a snapshot's ref lives. Sorted by name, which starts with its timestamp.
REFS: Final[str] = "refs/snapshots"
#: Where the specs a snapshot was rendered with live: same name as the snapshot's ref.
SPECS: Final[str] = "refs/specs"
#: The branch that always names the newest snapshot, so `git status` has something to answer against.
TRUNK: Final[str] = "refs/heads/main"
#: git's porcelain status codes, reduced to what the ledger cares about.
KINDS: Final[Mapping[str, Kind]] = {
    "?": "added",
    "A": "added",
    "C": "added",
    "M": "changed",
    "T": "changed",
    "R": "changed",
    "U": "changed",
    "D": "removed",
}


class StoreError(RuntimeError):
    """The store could not do what was asked: absent, or git refused."""


class Store:
    """The history of one config dir. Every method is a file operation with a pointer."""

    def __init__(
        self, work_tree: Path, git_dir: Path | None = None, exclude: Iterable[str] = (), include: Iterable[str] = ()
    ) -> None:
        """`exclude` protects the runtime from `clean`; `include` is the scope of a snapshot.

        Two mechanisms because git has two masters: the tree's own `.gitignore` outranks
        `info/exclude`, so a file it hides (the harness's `package.json` does exactly this)
        would silently vanish from history. An allowlist of forced pathspecs is the only
        scope a dirty tree cannot defeat; empty `include` keeps the plain `add --all` behaviour.
        """
        self.work_tree = work_tree.expanduser().resolve()
        self.git_dir = (git_dir or settings.global_.state_dir / f"{self.work_tree.name}.git").expanduser().resolve()
        self.exclude = tuple(exclude)
        self.include = tuple(include)

    # ---------------------------------------------------------------- public
    def ready(self) -> bool:
        """Whether a history exists here at all."""
        return (self.git_dir / "HEAD").is_file()

    def initialise(self) -> None:
        """Create the store and declare its scope. Safe to call on an existing one; a tree not yet laid is laid empty."""
        self.work_tree.mkdir(parents=True, exist_ok=True)
        self.git_dir.parent.mkdir(parents=True, exist_ok=True)
        self.ready() or self._git("init", "--quiet", "--initial-branch=main")
        self._git("config", "user.name", "op transpiler")
        self._git("config", "user.email", "op@e-nous.local")
        self._git("config", "gc.auto", "0")  # collection happens when retention says so, never mid-export
        (self.git_dir / "info").mkdir(parents=True, exist_ok=True)
        (self.git_dir / "info" / "exclude").write_text("".join(f"{pattern}\n" for pattern in self.exclude))

    def snapshot(self, reason: Reason, note: str = "") -> Snapshot | None:
        """Record the tree as it stands. Returns None when nothing moved — no hollow points."""
        self._require()
        self._stage()
        tree = self._git("write-tree").strip()
        if (current := self.head()) and self._tree_of(current.commit) == tree:
            return None
        commit = self._git("commit-tree", tree, "-m", f"{reason} {note}".strip()).strip()
        self._git("update-ref", TRUNK, commit)
        self._git("update-ref", f"{REFS}/{dt.datetime.now(dt.UTC):%Y%m%dT%H%M%S%f}", commit)
        return self.head()

    def changed(self) -> tuple[FileChange, ...]:
        """What the tree holds that the newest snapshot does not. Reads only."""
        self._require()
        entries = self._git("status", "--porcelain", "-z", "--no-renames").split("\0")
        return tuple(FileChange(path=entry[3:], kind=self._kind(entry[:2])) for entry in entries if len(entry) > 3)

    def diff(self, before: str, after: str) -> tuple[FileChange, ...]:
        """What moved between two snapshots, as paths with a verdict."""
        self._require()
        lines = self._git("diff", "--name-status", "-z", "--no-renames", before, after).split("\0")
        pairs = zip(lines[::2], lines[1::2], strict=False)
        return tuple(FileChange(path=path, kind=self._kind(code)) for code, path in pairs if path)

    def pending(self, pointer: str = "") -> tuple[FileChange, ...]:
        """What the work tree holds beyond a snapshot — the latest by default.

        Two readings, because git has two blind spots: `diff <point>` compares trees
        and would miss a corpus file no snapshot has carried yet (nothing was `add`ed,
        so it is no one's), while `status` sees the work tree only against the head.
        Diff for the point, status for what is new, merged into one verdict list.
        """
        self._require()
        if not pointer:
            return self.changed()
        lines = self._git("diff", "--name-status", "-z", "--no-renames", self.resolve(pointer).commit).split("\0")
        pairs = zip(lines[::2], lines[1::2], strict=False)
        moved = tuple(FileChange(path=path, kind=self._kind(code)) for code, path in pairs if path)
        fresh = self._git("ls-files", "--others", "--exclude-standard").splitlines()
        return moved + tuple(FileChange(path=path, kind="added") for path in fresh if path)

    def restore(self, commit: str) -> None:
        """Put the tree back exactly as that snapshot held it, and take nothing else with it.

        Tracked files return to their recorded content; files the snapshot never held are
        removed; everything the scope excludes — sessions, runtime trees — is untouched.
        """
        self._require()
        self._git("restore", "--source", commit, "--worktree", "--staged", "--", ".")
        self._git("clean", "--force", "-d", "--quiet")

    def read(self, commit: str, path: str) -> str:
        """What a snapshot held at that path, or "" when it held nothing there."""
        self._require()
        try:
            return self._git("show", f"{commit}:{path}")
        except StoreError:
            return ""

    def paths(self, commit: str) -> frozenset[str]:
        """Every path a snapshot recorded."""
        self._require()
        return frozenset(line for line in self._git("ls-tree", "-r", "--name-only", commit).splitlines() if line)

    def log(self, limit: int = 0) -> tuple[Snapshot, ...]:
        """Every recovery point, newest first."""
        self._require()
        listed = self._git(
            "for-each-ref",
            "--sort=-refname",
            f"--count={limit}" if limit else "--count=0",
            "--format=%(refname)%09%(objectname)%09%(creatordate:iso-strict)%09%(contents:subject)",
            REFS,
        )
        return tuple(self._point(line) for line in listed.splitlines() if line)

    def head(self) -> Snapshot | None:
        """The newest recovery point, or None on an empty store."""
        return next(iter(self.log(limit=1)), None)

    def resolve(self, token: str) -> Snapshot:
        """A point by its full ref, ref name, commit or commit prefix — the pointer a human types."""
        self._require()
        points = self.log()
        found = tuple(
            point
            for point in points
            if token in {point.ref, point.commit} or point.commit.startswith(token) or point.ref.endswith(f"/{token}")
        )
        if not found:
            raise StoreError(f"no snapshot matches {token!r}")
        if len(found) > 1:
            raise StoreError(f"{token!r} is ambiguous: {len(found)} snapshots match")
        return found[0]

    def seal(self, specs: Path) -> str:
        """Record `specs` as what the newest snapshot was rendered with; the commit that holds it."""
        head = self._require_head()
        commit = self._git("commit-tree", self._spec_tree(specs), "-m", f"specs of {head.commit[:10]}").strip()
        self._git("update-ref", self._spec_ref(head), commit)
        return commit

    def specs(self, specs: Path) -> tuple[FileChange, ...] | None:
        """The spec files moved since the newest snapshot was sealed; None when it never was."""
        head = self._require_head()
        try:
            sealed = self._git("rev-parse", "--verify", "--quiet", f"{self._spec_ref(head)}^{{tree}}").strip()
        except StoreError:
            return None
        lines = self._git(
            "diff-tree", "-r", "-z", "--name-status", "--no-renames", sealed, self._spec_tree(specs)
        ).split("\0")
        pairs = zip(lines[::2], lines[1::2], strict=False)
        return tuple(FileChange(path=path, kind=self._kind(code)) for code, path in pairs if path)

    def releasable(self, retention: Retention, now: dt.datetime | None = None) -> tuple[Snapshot, ...]:
        """The points retention no longer protects — what `prune` would release, read only."""
        self._require()
        moment = now or dt.datetime.now(dt.UTC)
        return tuple(
            point for index, point in enumerate(self.log()) if index and retention.expired(index, point.at, moment)
        )

    def prune(self, retention: Retention, now: dt.datetime | None = None) -> tuple[str, ...]:
        """Release the points retention no longer protects, then collect what they held.

        The newest point is never released, whatever the policy says: a history whose
        last state is unrecoverable is not a history.
        """
        doomed = self.releasable(retention, now)
        for point in doomed:
            self._git("update-ref", "-d", point.ref)
            self._git("update-ref", "-d", self._spec_ref(point))
        doomed and self._git("gc", "--prune=now", "--quiet")
        return tuple(point.commit for point in doomed)

    # --------------------------------------------------------------- private
    def _stage(self) -> None:
        """Stage the scope: force the allowlist past any `.gitignore`, or add everything.

        git refuses a pathspec that matches nothing, and a fresh tree lacks roots the render
        has not written yet. A root present is added; a root absent is dropped from the index,
        so its deletion is recorded instead of silently kept from the last snapshot. A root
        that is a symlink counts as absent: a link holds no content of its own, its target
        belongs to another tree, and the first export replaces it with real files.
        """
        if not self.include:
            self._git("add", "--all")
            return
        magic = tuple(spec for spec in self.include if spec.startswith(":"))
        roots = [spec for spec in self.include if not spec.startswith(":")]
        present = [root for root in roots if (path := self.work_tree / root).exists() and not path.is_symlink()]
        absent = [root for root in roots if root not in present]
        present and self._git("add", "--all", "-f", "--", *present, *magic)
        absent and self._git("rm", "-r", "--cached", "--quiet", "--ignore-unmatch", "--", *absent)

    def _require(self) -> None:
        if not self.ready():
            raise StoreError(f"not initialised: {self.git_dir}")

    def _git(self, *arguments: str) -> str:
        """Raw stdout: `status --porcelain` encodes a verdict in leading spaces, so nothing is stripped here."""
        done = subprocess.run(  # noqa: S603 — fixed binary, arguments never shell-interpreted
            ("git", f"--git-dir={self.git_dir}", f"--work-tree={self.work_tree}", *arguments),
            capture_output=True,
            text=True,
            cwd=self.work_tree,
        )
        if done.returncode:
            raise StoreError(f"git {arguments[0]}: {done.stderr.strip() or done.returncode}")
        return done.stdout

    def _require_head(self) -> Snapshot:
        self._require()
        if (head := self.head()) is None:
            raise StoreError("no snapshot yet: nothing to seal specs against")
        return head

    def _spec_tree(self, specs: Path) -> str:
        """The tree object of `specs` as it stands, written through a private index into this git dir."""
        with TemporaryDirectory(prefix="specs-index-") as tmp:
            env = os.environ | {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            base = ("git", f"--git-dir={self.git_dir}", f"--work-tree={specs.parent}")
            add = subprocess.run(
                (*base, "add", "-f", "--", specs.name),
                capture_output=True,
                text=True,  # noqa: S603
                cwd=specs.parent,
                env=env,
            )
            tree = subprocess.run(
                (*base, "write-tree"),
                capture_output=True,
                text=True,  # noqa: S603
                cwd=specs.parent,
                env=env,
            )
        if add.returncode or tree.returncode:
            raise StoreError(f"git specs tree: {(add.stderr or tree.stderr).strip()}")
        return tree.stdout.strip()

    @staticmethod
    def _spec_ref(point: Snapshot) -> str:
        return point.ref.replace(REFS, SPECS, 1)

    def _tree_of(self, commit: str) -> str:
        return self._git("show", "-s", "--format=%T", commit).strip()

    @staticmethod
    def _kind(code: str) -> Kind:
        return KINDS[next(char for char in code if char != " ")]

    @staticmethod
    def _point(line: str) -> Snapshot:
        ref, commit, at, subject = line.split("\t", 3)
        reason, _, note = subject.partition(" ")
        return Snapshot(commit=commit, at=dt.datetime.fromisoformat(at), reason=reason, note=note, ref=ref)  # ty: ignore[invalid-argument-type]
