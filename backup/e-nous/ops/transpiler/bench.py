"""transpiler.bench — the transpiler proven: does it replicate?

Zero LLM calls. `op transpiler check` asks whether the live tree matches the
render; this asks whether the render deserves to be trusted at all. Five gates,
each run against throwaway destinations, plus the live gate:

  determinism  two clean destinations, one run, byte-identical trees — modulo each tree's own path
  idempotence  a second export over an up-to-date tree writes nothing
  purity       core/ + specs/ alone are enough; the render never reads its output
  capability   replace keeps strangers, reset prunes only the orphans it governs
  fidelity     the backend's live tree mirrors its render (`op transpiler check`)

"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import msgspec

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.transpiler.render import Transpiler

#: Planted beside the corpus to prove the transpiler leaves runtime state alone.
STRANGERS: dict[str, str] = {
    "sessions/state.json": '{"autolearn": true}',
    "skills/synced/probe/SKILL.md": "runtime-owned skill",
    "plugins/autolearn.js": "// runtime plugin",
}
#: The orphan a reset must prune: one stale file in the first tree the backend governs.
ORPHAN = "deprecated.md"


class Gate(msgspec.Struct, frozen=True):
    """One property of the transpiler, proven or not."""

    name: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'}  {self.name:<12} {self.detail}"


class Bench:
    """Every gate over one backend's transpiler. Destinations are temporary; the live tree is read-only."""

    def __init__(self, backend: Backend = Backend.OPENCODE, out: Path | None = None, root: Path | None = None) -> None:
        self.root = (root or settings.ROOT).resolve()
        self.backend = backend
        self.out = out.expanduser().resolve() if out else settings.transpiler.live(backend)

    # ---------------------------------------------------------------- public
    def run(self) -> tuple[Gate, ...]:
        """Every gate, in order, against throwaway destinations."""
        with TemporaryDirectory(prefix="replication-") as tmp:
            bench = Path(tmp)
            return (
                self.determinism(bench / "a", bench / "b"),
                self.idempotence(bench / "a"),
                self.purity(bench / "pure"),
                self.capability(bench / "capability"),
                self.fidelity(),
            )

    def determinism(self, first: Path, second: Path) -> Gate:
        """The same corpus rendered twice into clean destinations must not differ by a byte.

        A config may name a path inside its own tree (an instruction file, a hook script), so
        each tree's root is read as one token: the destination is the only allowed difference.
        """
        self._export(first), self._export(second)
        left, right = self._tree(first), self._tree(second)
        odd = (left.keys() ^ right.keys()) | {path for path in left.keys() & right.keys() if left[path] != right[path]}
        return Gate(
            "determinism",
            not odd,
            f"{len(self._transpiler(first).files)} files identical" if not odd else f"divergent: {sorted(odd)}",
        )

    def idempotence(self, dst: Path) -> Gate:
        """Re-exporting an up-to-date tree is a no-op: nothing written, nothing pruned."""
        report = self._transpiler(dst).export()
        return Gate(
            "idempotence",
            not (report.written or report.pruned),
            f"second export wrote {len(report.written)}, pruned {len(report.pruned)}",
        )

    def purity(self, sandbox: Path) -> Gate:
        """core/ + specs/ must suffice: the render may never read what it wrote."""
        sandbox.mkdir(parents=True, exist_ok=True)
        for name in ("core", "specs"):
            (sandbox / name).is_symlink() or (sandbox / name).symlink_to(self.root / name)
        try:
            files = Transpiler(sandbox, self.backend, sandbox / "out").export().written
        except Exception as exc:  # noqa: BLE001 — surviving a bare corpus is the whole gate
            return Gate("purity", False, f"{type(exc).__name__}: {exc or '(no message)'}")
        return Gate("purity", True, f"{len(files)} files from core/ + specs/ alone")

    def capability(self, dst: Path) -> Gate:
        """replace must not touch what it does not render; reset prunes orphans, never strangers."""
        self._export(dst)
        orphan = min(self._transpiler(dst).governed()) / ORPHAN
        planted = {dst / rel: text for rel, text in STRANGERS.items()} | {orphan: "stale entry"}
        for path, text in planted.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

        kept = self._transpiler(dst).export("replace")
        intact = all(path.is_file() and path.read_text() == text for path, text in planted.items())
        swept = self._transpiler(dst).export("reset")
        spared = all((dst / rel).read_text() == text for rel, text in STRANGERS.items())

        passed = (
            intact
            and spared
            and not (kept.written or kept.pruned)
            and swept.pruned == (str(orphan.relative_to(dst)),)
            and not orphan.exists()
        )
        return Gate(
            "capability", passed, f"replace kept {len(planted)} strangers · reset pruned {swept.pruned or '()'}"
        )

    def fidelity(self) -> Gate:
        """The live gate: does the backend's own tree already mirror its render?"""
        drifts = self._transpiler(self.out).check()
        return Gate("fidelity", not drifts, f"{self.out} faithful" if not drifts else " · ".join(map(str, drifts)))

    # --------------------------------------------------------------- private
    def _transpiler(self, out: Path) -> Transpiler:
        return Transpiler(self.root, self.backend, out)

    def _export(self, dst: Path) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        self._transpiler(dst).export()

    @staticmethod
    def _tree(root: Path) -> dict[str, bytes]:
        """Every file of a rendered tree, its own root path replaced by one token."""
        anchor = bytes(root.resolve())
        return {
            str(path.relative_to(root)): path.read_bytes().replace(anchor, b"<out>")
            for path in root.rglob("*")
            if path.is_file()
        }
