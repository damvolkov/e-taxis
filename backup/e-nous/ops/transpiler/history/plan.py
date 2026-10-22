"""transpiler.history.plan — what a transpile would do, read before it does it.

A two-way comparison says the render and the harness differ. It cannot say whether
exporting is safe, because it does not know which side moved. That question has an
answer only with a third point: the last snapshot the store recorded.

    base    what the store last recorded
    live    what the harness holds now
    render  what core would produce now

    live == base, render != base   →  core moved      exporting is safe
    live != base, render == base   →  the harness moved, exporting would destroy it
    live != base, render != base   →  diverged, and it is decided file by file
    live == base, render == base   →  settled

Beside the moves, the plan names the spec files that changed since the base was sealed
(`Store.seal`): how the tree is made can move without a rendered byte moving with it.

The middle row is not hypothetical: research landed straight into three `lib.md`
files of the live harness while this module was being written, and a plain export
would have erased it without a word.

Plan before apply, which is the discipline `ops-gen-iac` states for infrastructure
and which this borrows wholesale.
"""

from __future__ import annotations

from collections.abc import Mapping
from difflib import unified_diff
from functools import cached_property
from pathlib import Path
from typing import Final, Literal, Protocol, runtime_checkable

import msgspec

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.models.history import Bump, Change, FileChange, Kind, Snapshot
from ops.transpiler.history.classify import Classifier
from ops.transpiler.history.matrix import Matrix
from ops.transpiler.history.store import Store

#: Which side moved since the last recorded point.
type Direction = Literal["core", "harness", "diverged", "settled", "unbased"]

#: The three-way read: (did the harness move, did the render move) → who moved.
#: The verdict function; its human prose lives in `view.py`, never here.
VERDICTS: Final[Mapping[tuple[bool, bool], Direction]] = {
    (True, True): "diverged",
    (True, False): "harness",
    (False, True): "core",
    (False, False): "settled",
}


@runtime_checkable
class Render(Protocol):
    """All the planner needs of a transpiler: where it writes, what it would write, for whom.

    A port, not the class — the planner compares three points and has no business
    knowing how the third one is produced. `backend` is not used to compute the plan;
    it names the render in the report so the reader knows which core produced it.
    """

    out: Path
    backend: Backend
    files: Mapping[Path, str]

    def owned(self, path: Path, text: str) -> str:
        """The part of a file's text the render owns — all of it, unless its spec owns only some keys."""
        ...

    def merged(self, path: Path, text: str) -> str:
        """What an export would write over the live file: the render, never dropping what is there."""
        ...


class Move(msgspec.Struct, frozen=True):
    """One path, interpreted and placed: what changed, and which side changed it.

    `before`/`after` are the two versions the classifier read — the change itself,
    carried by the model so the report can diff it and the changelog can later hold
    it without going back to git. Which pair depends on the verdict: what the harness
    did to the recorded state (`harness`), or what the export would do to the live one.
    """

    change: Change
    direction: Direction
    before: str = ""
    after: str = ""

    @property
    def destructive(self) -> bool:
        """Whether applying the transpile would overwrite work only the harness holds."""
        return self.direction in {"harness", "diverged"}

    @property
    def sides(self) -> tuple[str, str]:
        """How to name the two versions: who held each."""
        return ("recorded", "live") if self.direction == "harness" else ("live", "render")

    def diff(self, context: int = 2) -> str:
        """Unified diff of the change, labels included — the move's substance in one block."""
        left, right = self.sides
        return "\n".join(
            unified_diff(self.before.splitlines(), self.after.splitlines(), left, right, lineterm="", n=context)
        )

    def __str__(self) -> str:
        return f"{self.direction:<9} {self.change}"


class Plan(msgspec.Struct, frozen=True):
    """The data model of a transpile: what would move, which side moved it, what it costs.

    Pure payload. `apply` executes these moves, the ledger will persist this very
    struct as JSON, and `view.py` renders it — the presentation is never here.
    `settled` counts the paths where the three points agree: silence with a number.
    `specs` lists the spec files moved since the base was sealed; `sealed` is False when
    the base carries no seal yet, and then `specs` says nothing.
    """

    moves: tuple[Move, ...] = ()
    bump: Bump = "none"
    base: Snapshot | None = None
    settled: int = 0
    live: str = ""
    core: str = ""
    specs: tuple[FileChange, ...] = ()
    sealed: bool = False

    @property
    def destructive(self) -> tuple[Move, ...]:
        """The moves that would lose work. An export past these needs a human."""
        return tuple(move for move in self.moves if move.destructive)

    @property
    def empty(self) -> bool:
        return not self.moves

    @property
    def unsealed(self) -> bool:
        """Whether an apply has specs to seal: some moved, or the base never carried a seal."""
        return bool(self.specs) or not self.sealed

    def section(self, direction: Direction) -> tuple[Move, ...]:
        """The moves of one verdict, ordered by path."""
        return tuple(sorted((m for m in self.moves if m.direction == direction), key=lambda m: m.change.target))


class Planner:
    """Compares the three points and reports, without writing anything.

    Two ports, two consumers: the render answers *what core would write* (out and
    files only), the classifier answers *what the corpus claims* (the specs behind
    it). One `Transpiler` satisfies both, and the CLI wires it to each; a test can
    dictate the render without faking the whole spec model.
    """

    def __init__(
        self,
        render: Render,
        store: Store | None,
        classifier: Classifier,
        matrix: Matrix | None = None,
        specs: Path | None = None,
    ) -> None:
        """Render and classifier are injected, never defaulted: defaulting them would mean
        importing the transpiler here, and the transpiler mounts these commands. The CLI
        is the composition root; a test dictates its own render."""
        self.render = render
        self.store = store or Store(render.out)
        self.classifier = classifier
        self.matrix = matrix or Matrix()
        self.specs = specs

    # ---------------------------------------------------------------- public
    def plan(self) -> Plan:
        """What a transpile would change, which side changed it, and the bump it forces."""
        base = self.store.head() if self.store.ready() else None
        judged = [(path, self._move(path, base)) for path in sorted(self._paths(base))]
        moves = tuple(move for _, move in judged if move is not None)
        graded = tuple(move.change.grade for move in moves if move.change.grade)
        specs = self.store.specs(self.specs) if base and self.specs else None
        return Plan(
            moves=moves,
            bump=self.matrix.bump(graded),
            base=base,
            settled=sum(1 for _, move in judged if move is None),
            live=str(self.render.out),
            core=f"{self.render.backend} (core)",
            specs=specs or (),
            sealed=specs is not None,
        )

    # --------------------------------------------------------------- private
    @cached_property
    def _rendered(self) -> dict[str, str]:
        """What core would produce, keyed the way the store keys its paths."""
        return {str(path.relative_to(self.render.out)): text for path, text in self.render.files.items()}

    def _paths(self, base: Snapshot | None) -> frozenset[str]:
        """Every path any of the three points knows about, minus the trees a runtime owns:
        a base sealed before a tree was declared third-party still holds it, and no spec claims it."""
        recorded = self.store.paths(base.commit) if base else frozenset()
        return frozenset(
            path
            for path in frozenset(self._rendered) | recorded
            if not settings.layout.third_party & set(Path(path).parts)
        )

    def _move(self, path: str, base: Snapshot | None) -> Move | None:
        target = self.render.out / path
        before = self.render.owned(target, self.store.read(base.commit, path)) if base else ""
        live = self.render.owned(target, self._live(path))
        render = self.render.owned(target, self.render.merged(target, self._rendered.get(path, "")))
        if live == render:
            return None
        direction = self._direction(before, live, render, based=base is not None)
        kind = self._kind(live, render, direction)
        left, right = self._sides(before, live, render, direction)
        change = self.classifier.of(FileChange(path=path, kind=kind), left, right)
        return Move(change=change, direction=direction, before=left, after=right)

    def _live(self, path: str) -> str:
        """What the tree holds at a path — nothing under a linked root: that content is another tree's."""
        target, root = self.render.out / path, self.render.out / Path(path).parts[0]
        return target.read_text() if target.is_file() and not root.is_symlink() else ""

    @staticmethod
    def _direction(before: str, live: str, render: str, based: bool) -> Direction:
        if not based:
            return "unbased"
        return VERDICTS[(live != before, render != before)]

    @staticmethod
    def _kind(live: str, render: str, direction: Direction) -> Kind:
        """What applying the transpile would do to this path."""
        return "added" if not live and render else "removed" if live and not render else "changed"

    @staticmethod
    def _sides(before: str, live: str, render: str, direction: Direction) -> tuple[str, str]:
        """Which two versions the classifier should read the slots from.

        When the harness moved, the interesting diff is what it did to the recorded base;
        otherwise it is what the transpile would do to what is live right now.
        """
        return (before, live) if direction == "harness" else (live, render)
