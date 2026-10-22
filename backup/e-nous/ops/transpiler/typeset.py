"""transpiler.typeset — one persona document spec, read both ways, deterministic.

Forward, a registry of slots becomes the document the spec declares: blocks in order,
empty slots skipped, a block with nothing in it not rendered, the harness's `limit`
enforced here so nothing is ever truncated downstream. The render also yields where each
slot landed (`spans`) — the source map the inverse needs, kept out of the text so no
marker ever reaches a prompt or a harness editor.

Backward, a document is read into its blocks (`parse`), the parts the harness owns cut
out first (`strip`). A region is the harness's: it never counts as drift, it is carried
over when the render is written (`merge`), and nothing in it is ever absorbed. A block
whose body moved is split back into its slots (`split`): every edit is placed by the span
it falls in, and an edit no single slot can own makes the split refuse rather than guess.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from difflib import SequenceMatcher
from functools import cached_property, reduce
from itertools import accumulate, pairwise
from typing import Final

from ops.models.spec import Block, Document, Region

#: An `## heading` line: where a document's body splits into its h2 blocks.
H2_RE: Final = re.compile(r"^## (.+?)[ \t]*$", re.M)
#: Three or more newlines: the gap a cut region leaves, closed back to one blank line.
GAP_RE: Final = re.compile(r"\n{3,}")

#: What each block form puts before its joined slots.
PREFIX: Final[Mapping[str, str]] = {"h1": "# ", "para": "", "quote": "> ", "h2": "## {heading}\n\n"}

type Spans = dict[str, tuple[int, int]]
#: One edit of a block body, as difflib states it: tag, reference range, body range.
type Opcode = tuple[str, int, int, int, int]


class Typeset:
    """One document spec: slots → text and spans, text → blocks, regions apart."""

    def __init__(self, document: Document) -> None:
        self.document = document

    ##### PRIVATE #####

    def _render_build(self, slots: Mapping[str, str]) -> tuple[str, Spans]:
        """The document and the span of every slot in it: blocks built alone, then laid end to end."""
        built = [found for block in self.document.blocks if (found := self._render_block(block, slots))]
        starts = accumulate((len(text) + 2 for text, _ in built), initial=0)
        spans = {
            slot: (start + begin, start + end)
            for (_, local), start in zip(built, starts, strict=False)
            for slot, (begin, end) in local.items()
        }
        return "\n\n".join(text for text, _ in built), spans

    def _render_block(self, block: Block, slots: Mapping[str, str]) -> tuple[str, Spans] | None:
        """One block and its slots' spans inside it, or None when every slot is empty."""
        present = [(slot, text) for slot in block.slots if (text := self._render_slot(slot, slots))]
        if not present:
            return None
        prefix = PREFIX[block.type].format(heading=block.heading)
        starts = accumulate((len(text) + len(block.join) for _, text in present), initial=len(prefix))
        spans = {slot: (start, start + len(text)) for (slot, text), start in zip(present, starts, strict=False)}
        return prefix + block.join.join(text for _, text in present), spans

    def _render_slot(self, slot: str, slots: Mapping[str, str]) -> str:
        if (text := slots.get(slot)) is None:
            raise ValueError(f"{self.document.target}: slot {slot!r} is declared by no layer the harness renders")
        return text.strip("\n")

    def _common_cuts(self, text: str) -> list[tuple[int, int]]:
        """Where the harness's regions sit in a text, in order."""
        return sorted(
            match.span() for region in self.document.regions for match in self._patterns[region].finditer(text)
        )

    @staticmethod
    def _split_owner(spans: list[tuple[str, int, int]], anchors: list[tuple[str, int]], op: Opcode) -> str | None:
        """The one slot an edit belongs to: an empty slot sitting where text is inserted, else the span holding the edit."""
        tag, start, end, _, _ = op
        sitting = [slot for slot, at in anchors if tag == "insert" and at == start]
        holding = [slot for slot, begin, finish in spans if begin <= start and end <= finish]
        return sitting[0] if len(sitting) == 1 else None if sitting else holding[0] if holding else None

    @staticmethod
    def _split_apply(text: str, origin: int, edits: list[tuple[int, int, str]]) -> str:
        """A slot's text with its edits applied, right to left so earlier offsets stay true."""
        return reduce(
            lambda acc, e: acc[: e[0] - origin] + e[2] + acc[e[1] - origin :], sorted(edits, reverse=True), text
        )

    @cached_property
    def _patterns(self) -> Mapping[Region, re.Pattern]:
        return {region: self._compile(region) for region in self.document.regions}

    @staticmethod
    def _compile(region: Region) -> re.Pattern:
        match region.kind:
            case "heading":
                return re.compile(rf"^## {re.escape(region.match)}[ \t]*$[\s\S]*?(?=^## |\Z)", re.M)
            case "marker":
                return re.compile(rf"(?:{region.start})[\s\S]*?(?:{region.end})")

    @staticmethod
    def _parse_preamble(preamble: str) -> dict[str, str]:
        """Title, paragraphs and quote before the first h2, told apart by how they are typeset."""
        chunks = [chunk for chunk in preamble.strip("\n").split("\n\n") if chunk.strip()]
        h1 = next((chunk for chunk in chunks[:1] if chunk.startswith("# ")), None)
        rest = chunks[1:] if h1 is not None else chunks
        found = {
            "h1": h1[2:] if h1 is not None else "",
            "quote": "\n\n".join(chunk[2:] for chunk in rest if chunk.startswith("> ")),
            "para": "\n\n".join(chunk for chunk in rest if not chunk.startswith("> ")),
        }
        return {key: value for key, value in found.items() if value}

    ############################################################

    ##### PUBLIC #####

    def render(self, slots: Mapping[str, str]) -> str:
        """The document, or a refusal when it outgrows the harness's cap."""
        text, _ = self._render_build(slots)
        if self.document.limit and len(text) > self.document.limit:
            raise ValueError(f"{self.document.target}: {len(text)} chars > limit {self.document.limit}")
        return text

    def spans(self, slots: Mapping[str, str]) -> Spans:
        """Where each non-empty slot sits in the render: the source map of the inverse."""
        return self._render_build(slots)[1]

    def strip(self, text: str) -> str:
        """The text without the harness's regions — what the render owns, in the form it is compared."""
        if not (cuts := self._common_cuts(text)):
            return text
        kept = "".join(text[left[1] : right[0]] for left, right in pairwise([(0, 0), *cuts, (len(text), 0)]))
        return GAP_RE.sub("\n\n", kept).strip("\n")

    def regions(self, text: str) -> tuple[str, ...]:
        """The harness's regions as they stand in a text, in order."""
        return tuple(text[start:end].strip("\n") for start, end in self._common_cuts(text))

    def merge(self, rendered: str, live: str) -> str:
        """The render, then every heading of the live file no block declares, then the harness's regions: nothing live is dropped."""
        kept = (
            "\n\n".join(part for part in (key, body) if part)
            for key, body in self.parse(live).items()
            if key.startswith("## ")
        )
        return rendered + "".join(f"\n\n{part}" for part in (*kept, *self.regions(live)))

    def parse(self, text: str) -> dict[str, str]:
        """A document read back into its blocks, regions cut first: block key → body.

        A heading no block declares keeps its own key (`## <heading>`): the caller decides
        what an unplaced block means — it is never folded into a neighbour.
        """
        owned = self.strip(text)
        heads = list(H2_RE.finditer(owned))
        declared = {block.heading for block in self.document.blocks if block.type == "h2"}
        ends = [*(head.start() for head in heads[1:]), len(owned)][: len(heads)]
        sections = {
            (head.group(1) if head.group(1) in declared else f"## {head.group(1)}"): owned[head.end() : end].strip("\n")
            for head, end in zip(heads, ends, strict=True)
        }
        return self._parse_preamble(owned[: heads[0].start()] if heads else owned) | sections

    def split(self, block: Block, slots: Mapping[str, str], body: str) -> dict[str, str] | None:
        """A block's new body divided back into its slots, measured against the body `slots` render.

        Only the slots an edit touched are returned. None when an edit straddles two slots,
        touches the join between them, or lands where two empty slots sit: the caller treats
        that as a conflict. The caller also re-renders the result and compares — the split
        proposes, the fixpoint decides.
        """
        if len(block.slots) == 1:
            return {block.slots[0]: body}
        texts = [(slot, self._render_slot(slot, slots)) for slot in block.slots]
        present = [(slot, text) for slot, text in texts if text]
        reference = block.join.join(text for _, text in present)
        starts = accumulate((len(text) + len(block.join) for _, text in present), initial=0)
        spans = [(slot, start, start + len(text)) for (slot, text), start in zip(present, starts, strict=False)]
        ends = [(block.slots.index(slot), end) for slot, _, end in spans]
        anchors = [
            (slot, max((end for index, end in ends if index < block.slots.index(slot)), default=0))
            for slot, text in texts
            if not text
        ]
        ops = [op for op in SequenceMatcher(None, reference, body, autojunk=False).get_opcodes() if op[0] != "equal"]
        owners = [self._split_owner(spans, anchors, op) for op in ops]
        if None in owners:
            return None
        origin = {slot: start for slot, start, _ in spans}
        current = dict(texts)
        edits = {
            slot: [
                (i1, i2, body[j1:j2]) for (_, i1, i2, j1, j2), owner in zip(ops, owners, strict=True) if owner == slot
            ]
            for slot in dict.fromkeys(owner for owner in owners if owner)
        }
        return {
            slot: self._split_apply(current[slot], origin[slot], found)
            if slot in origin
            else "".join(text for _, _, text in found).removeprefix(block.join).removesuffix(block.join).strip("\n")
            for slot, found in edits.items()
        }
