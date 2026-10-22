"""transpiler.bridge — the transpiler's inverse for skills: flat SKILL.md → structured core/, deterministic.

External tools understand the flat form; core/ is structured. A run renders one
skill into the flat form a tool edits (`view`) and, when the tool edited the skill
directly, folds the edit back (`reverse`). Nothing is guessed: the body returns to
the instructions source, listed references return byte for byte, and anything the
inverse cannot place is reported, never written.

Two things are never reversed:

  · the frontmatter — the description is routing text with its own owner, the
    activation gate; a tool that rewrote it gets a conflict, not a win;
  · a learned block (`<!-- SKILLOPT-SLEEP:LEARNED … -->`). An optimizer appends
    lessons; a skill integrates them. `lessons()` extracts them for the integrator,
    and a body that still carries the block is refused as unintegrated.

`reverse(view(skill)) == skill` byte for byte is the fixpoint every candidate is checked on.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import eserde
import msgspec

from ops.core.settings import settings
from ops.models.entity import Backend, Entity
from ops.transpiler.render import Transpiler

BLOCK_RE: Final = re.compile(r"<!-- SKILLOPT-SLEEP:LEARNED START -->(.*?)<!-- SKILLOPT-SLEEP:LEARNED END -->", re.S)
_BULLET_RE: Final = re.compile(r"^- (.+)$", re.M)


class BridgeChange(msgspec.Struct, frozen=True, array_like=True):
    """One source file the inverse wrote, and why."""

    kind: str
    path: str


class BridgeResult(msgspec.Struct, frozen=True):
    """Everything one reverse did and everything it refused to do."""

    changes: tuple[BridgeChange, ...] = ()
    conflicts: tuple[str, ...] = ()
    unlisted: tuple[str, ...] = ()


class Bridge:
    """Skills only: the one entity whose body an external optimizer evolves."""

    def __init__(self, root: Path, backend: Backend = Backend.CLAUDECODE) -> None:
        self.root = root
        self.backend = backend

    ##### PRIVATE #####

    def _common_transpiler(self, out: Path) -> Transpiler:
        return Transpiler(self.root, self.backend, out)

    def _common_dir(self, ident: str) -> Path:
        return self.root / settings.layout.core()[Entity.SKILL] / ident

    @staticmethod
    def _view_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    @staticmethod
    def _reverse_split(text: str, ident: str) -> tuple[str, str]:
        """Inverse of the transpiler's compose for a titled skill: (frontmatter block, body)."""
        head, sep, rest = text.partition("\n---\n")
        return head + "\n---", rest.removeprefix("\n").removeprefix(f"# {ident}\n\n") if sep else ""

    ############################################################

    ##### PUBLIC #####

    def view(self, ident: str, out: Path) -> Path:
        """Render one skill flat under `out/skills/<ident>/`, references beside it."""
        tp = self._common_transpiler(out)
        target = out / "skills" / ident
        files = {path: text for path, text in tp.files.items() if path.is_relative_to(target)}
        [self._view_write(path, text) for path, text in files.items()]
        return target / "SKILL.md"

    def reverse(self, ident: str, flat: Path) -> BridgeResult:
        """Fold an edited flat SKILL.md (and its references dir) back into `root/core/tekton/skills/<ident>`."""
        tp = self._common_transpiler(flat.parent)
        spec = tp.spec(Entity.SKILL)
        assert spec and spec.flat
        sdir = self._common_dir(ident)
        data = eserde.load(sdir / spec.structured_manifest)
        front, body = self._reverse_split(flat.read_text(), ident)
        conflicts = (
            () if front == tp._frontmatter(spec.flat, data) else (f"{ident}: frontmatter changed in {flat.name}",)
        )
        listed = set(data.get(spec.references.slot, []))
        changes: list[BridgeChange] = []
        if BLOCK_RE.search(body):
            return BridgeResult(
                conflicts=(*conflicts, f"{ident}: unintegrated learned block — integrate it, never copy it")
            )
        source = sdir / data[spec.flat.body_slot]["source"]
        if source.read_text().rstrip() != body.rstrip():
            source.write_text(body.rstrip() + "\n")
            changes.append(BridgeChange("body", str(source.relative_to(self.root))))
        moved = [
            ref
            for ref in sorted(listed)
            if (flat.parent / ref).is_file() and (flat.parent / ref).read_text() != (sdir / ref).read_text()
        ]
        [(sdir / ref).write_text((flat.parent / ref).read_text()) for ref in moved]
        changes += [BridgeChange("reference", str((sdir / ref).relative_to(self.root))) for ref in moved]
        refdir = flat.parent / spec.references.dir
        present = (
            sorted(str(p.relative_to(flat.parent)) for p in refdir.rglob("*") if p.is_file()) if refdir.is_dir() else []
        )
        return BridgeResult(
            changes=tuple(changes), conflicts=conflicts, unlisted=tuple(ref for ref in present if ref not in listed)
        )

    def fixpoint(self, ident: str) -> bool:
        """`reverse(view(skill)) == skill`, byte for byte, on a throwaway copy of the corpus."""
        with TemporaryDirectory(prefix="bridge-fixpoint-") as tmp:
            copy = Path(tmp) / "root"
            shutil.copytree(self.root / "core", copy / "core")
            (copy / settings.layout.specs).symlink_to(self.root / settings.layout.specs)
            twin = Bridge(copy, self.backend)
            result = twin.reverse(ident, twin.view(ident, Path(tmp) / "flat"))
            return not (result.changes or result.conflicts)

    @staticmethod
    def lessons(*texts: str) -> tuple[str, ...]:
        """Every bullet inside any learned block of the given texts, first occurrence kept, in order."""
        found = [
            line.strip() for text in texts for block in BLOCK_RE.findall(text) for line in _BULLET_RE.findall(block)
        ]
        return tuple(dict.fromkeys(found))
