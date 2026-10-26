"""transpiler.absorb — the render's inverse for persona documents: what the harness wrote, folded back into core/.

A harness that learns rewrites its own files: OpenHuman's persona editor, Claude's `#`
memory, an agent with a write tool. `plan` already says *who* moved a file; absorb acts
on the answer the other way round. It reads three points per block of every document
the spec declares — what the store recorded, what the harness holds, what core renders —
and only a block the harness alone moved is absorbed:

    live == render                       settled    (nothing, or both made the same edit)
    live == recorded                     core       (the export's job, not this one)
    render == recorded, live != it       harness    → split back into its slots, written
    all three differ                     diverged   → held; `take harness` lets the harness win

Nothing is guessed. A moved block is split by the span each edit falls in (`Typeset.split`);
an edit two slots could own, a heading no block declares, a slot inline in its manifest,
a document with no recorded point — each is held and named, never written. What is
written must re-render to exactly the live block (the fixpoint), or it is held too. The
harness's regions (a learner's managed blocks) are reported as learned and never absorbed.

`run` decides and touches nothing; `write` lands the slots in core/ — files only, never a
commit. Persona is identity: a human reads `git diff` and decides.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

import msgspec

from ops.models.spec import Block, Document
from ops.transpiler.render import Transpiler
from ops.transpiler.typeset import Typeset

#: Which side a block moved on since the recorded point.
type Direction = Literal["settled", "core", "harness", "diverged", "unplaced", "held"]
#: Who wins a diverged block: nobody (the recorded three-way), or the harness.
type Take = Literal["recorded", "harness"]

#: The directions that leave a block where it is, and why — what the report prints beside it.
WHY: Final[Mapping[str, str]] = {
    "core": "core moved: the export lands it",
    "diverged": "both moved: decide, or take harness",
    "unplaced": "no block declares this heading",
}


class AbsorbSlot(msgspec.Struct, frozen=True):
    """One slot the harness rewrote: where it lives in core/, and its text before and after."""

    document: str
    slot: str
    path: str
    before: str
    after: str


class AbsorbBlock(msgspec.Struct, frozen=True):
    """One block absorb leaves where it is, and why."""

    document: str
    block: str
    direction: Direction
    reason: str


class AbsorbReport(msgspec.Struct, frozen=True):
    """What one absorb would write, what it holds, and what the harness learned on its own."""

    slots: tuple[AbsorbSlot, ...] = ()
    held: tuple[AbsorbBlock, ...] = ()
    learned: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.slots

    def __str__(self) -> str:
        return "\n".join(
            (
                *(f"absorb   {s.document} · {s.slot} → {s.path}" for s in self.slots),
                *(f"{b.direction:<8} {b.document} · {b.block}: {b.reason}" for b in self.held),
                *(f"learned  {region.splitlines()[0]}" for region in self.learned),
                f"{len(self.slots)} slots to absorb · {len(self.held)} held · {len(self.learned)} learned regions",
            )
        )


class Absorb:
    """One backend's persona documents, read back against core/ and the recorded point."""

    def __init__(self, render: Transpiler, recorded: Mapping[str, str] | None, take: Take = "recorded") -> None:
        """`recorded` maps each document target to its text at the store's newest point; None when unbased."""
        self.render = render
        self.recorded = recorded
        self.take = take

    ##### PRIVATE #####

    def _run_document(self, doc: Document) -> tuple[list[AbsorbSlot], list[AbsorbBlock], tuple[str, ...]]:
        """Every slot of one document the harness alone moved, and every block left where it is."""
        if not (path := self.render.out / doc.target).is_file():
            return [], [AbsorbBlock(doc.target, "*", "held", "absent from the harness")], ()
        typeset, live = Typeset(doc), path.read_text()
        try:
            rendered = typeset.render(self.render.persona)
        except ValueError as exc:
            return [], [AbsorbBlock(doc.target, "*", "held", f"core does not render: {exc}")], ()
        if (recorded := self._run_recorded(doc)) is None:
            return [], [AbsorbBlock(doc.target, "*", "held", "unbased: no recorded point — init, or take harness")], ()
        old, now, new = typeset.parse(recorded), typeset.parse(live), typeset.parse(rendered)
        held = [AbsorbBlock(doc.target, key, "unplaced", WHY["unplaced"]) for key in now if key.startswith("## ")]
        placed = {block.key: self._run_block(typeset, block, old, now, new) for block in doc.blocks}
        held += [
            AbsorbBlock(doc.target, key, d, why)
            for key, (d, why, _) in placed.items()
            if d not in {"settled", "harness"}
        ]
        found = {key: updates for key, (d, _, updates) in placed.items() if d == "harness" and updates}
        kept, refused = self._run_fixpoint(typeset, found, now)
        held += [AbsorbBlock(doc.target, key, "held", why) for key, why in refused]
        slots = [
            AbsorbSlot(doc.target, slot, str(source.relative_to(self.render.root)), self.render.persona[slot], text)
            for slot, text in kept.items()
            if (source := self.render.sources.get(slot)) is not None
        ]
        held += [
            AbsorbBlock(doc.target, slot, "held", "inline in its manifest: edit persona.yaml by hand")
            for slot in kept
            if self.render.sources.get(slot) is None
        ]
        return slots, held, typeset.regions(live)

    def _run_recorded(self, doc: Document) -> str | None:
        """The text the block verdicts measure against: the recorded point, or the render when the harness is taken unbased."""
        found = self.recorded.get(doc.target) if self.recorded is not None else None
        harness_unbased = found is None and self.take == "harness"
        return Typeset(doc).render(self.render.persona) if harness_unbased else found

    def _run_block(
        self, typeset: Typeset, block: Block, old: Mapping[str, str], now: Mapping[str, str], new: Mapping[str, str]
    ) -> tuple[Direction, str, dict[str, str]]:
        """One block's direction and, when the harness is to win it, the slots it splits into."""
        recorded, live, rendered = (side.get(block.key, "") for side in (old, now, new))
        direction: Direction = (
            "settled"
            if live == rendered
            else "core"
            if live == recorded
            else "harness"
            if rendered == recorded or self.take == "harness"
            else "diverged"
        )
        if direction != "harness":
            return direction, WHY.get(direction, ""), {}
        split = typeset.split(block, self.render.persona, live)
        return ("harness", "", split) if split is not None else ("held", "an edit no single slot owns", {})

    def _run_fixpoint(
        self, typeset: Typeset, found: Mapping[str, dict[str, str]], now: Mapping[str, str]
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """The splits whose re-render reproduces the live block exactly; the rest, refused with the reason."""
        proposed = dict(self.render.persona) | {
            slot: text for updates in found.values() for slot, text in updates.items()
        }
        try:
            again = typeset.parse(typeset.render(proposed))
        except ValueError as exc:
            return {}, [(key, f"absorbed text does not render: {exc}") for key in found]
        faithful = {key: updates for key, updates in found.items() if again.get(key, "") == now.get(key, "")}
        refused = [(key, "re-render would not reproduce the live block") for key in found if key not in faithful]
        return {slot: text for updates in faithful.values() for slot, text in updates.items()}, refused

    ############################################################

    ##### PUBLIC #####

    def run(self) -> AbsorbReport:
        """Decide, document by document; nothing is written."""
        parts = [self._run_document(doc) for doc in self.render.documents]
        return AbsorbReport(
            slots=tuple(slot for slots, _, _ in parts for slot in slots),
            held=tuple(block for _, held, _ in parts for block in held),
            learned=tuple(region for _, _, learned in parts for region in learned),
        )

    def write(self, report: AbsorbReport) -> tuple[Path, ...]:
        """Land every absorbed slot in its core/ file — a trailing newline, as the corpus keeps them. Never a commit."""
        written = tuple(self.render.root / slot.path for slot in report.slots)
        for path, slot in zip(written, report.slots, strict=True):
            path.write_text(f"{slot.after}\n" if slot.after else "")
        return written
