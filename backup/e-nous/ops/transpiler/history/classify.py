"""transpiler.history.classify — read a flat path back into the entity it belongs to, and a diff into slots.

git says `M skills/test-py-tdd/SKILL.md`. The ledger needs *skill `test-py-tdd`, the rule
body moved, guidance, minor*. Nothing here is hand-written knowledge of the corpus: every
route is inverted from the same `spec.flat.path` the transpiler renders with, so a spec
that changes shape moves the classifier with it and a path no spec claims is not corpus.

One distinction carries most of the weight. A path is either an entity's **target** — its
SKILL.md, its agent file — or one of its **slots**, a reference beside it. A target that
appears is a new entity and weighs as surface; a reference that appears is an existing
entity growing depth and weighs as deepening. Same verb, different subject.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from functools import cached_property
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

import eserde
import msgspec

from ops.models.entity import INSTANCED, Entity
from ops.models.history import Change, FileChange, Kind
from ops.models.spec import FM_RE, Document, Spec
from ops.transpiler.history.matrix import Matrix
from ops.transpiler.typeset import Typeset

#: The slot a persona block no spec declares moves: a harness grew a heading the corpus does not know.
UNPLACED: Final[str] = "unplaced"


class Site(msgspec.Struct, frozen=True):
    """Where a flat path lands in the corpus: the entity, which one, and — if the path is
    itself a slot rather than the entity's target — which slot."""

    entity: Entity
    id: str = ""
    subentity: str = ""
    slot: str = ""

    @property
    def is_target(self) -> bool:
        """Whether the path is the entity itself, so appearing or vanishing is its lifecycle."""
        return not self.slot


class Route(msgspec.Struct, frozen=True):
    """One compiled way a path may belong to an entity."""

    pattern: re.Pattern
    entity: Entity
    slotted: bool = False
    slot: str = ""  # a path that is always one slot (a config text file, an asset)

    def match(self, path: str) -> Site | None:
        if (found := self.pattern.fullmatch(path)) is None:
            return None
        named = found.groupdict()
        return Site(
            entity=self.entity,
            id=named.get("id", "") or "",
            subentity=path if self.entity in {Entity.CONFIG, Entity.PERSONA} else "",
            slot=f"references/{named['file']}" if self.slotted else self.slot,
        )


@runtime_checkable
class Claims(Protocol):
    """All the classifier needs of a transpiler: which shapes the corpus declares.

    A port, the render's mirror — the planner reads what core would write, the
    classifier reads what core claims to own, and one `Transpiler` answers both.
    """

    def spec(self, entity: Entity) -> Spec | None: ...

    def find(self, name: str, needs: str) -> Spec | None: ...


class Classifier:
    """Turns what the store saw into what the ledger records."""

    def __init__(self, claims: Claims, matrix: Matrix | None = None) -> None:
        """Claims are injected, never defaulted: importing the transpiler to default them
        would close the cycle this split exists to break. The CLI is the composition root."""
        self.claims = claims
        self.matrix = matrix or Matrix()

    # ---------------------------------------------------------------- public
    def locate(self, path: str) -> Site | None:
        """Which entity a flat path belongs to, or None when no spec claims it."""
        return next((site for route in self.routes if (site := route.match(path))), None)

    def of(self, change: FileChange, before: str = "", after: str = "") -> Change:
        """One path, interpreted: entity, slots that moved, and the grade they carry."""
        site = self.locate(change.path)
        if site is None:
            raise KeyError(f"{change.path}: no spec claims this path")
        slots = self._slots(site, change.kind, before, after)
        kind: Kind = change.kind if site.is_target else "changed"
        grade = self.matrix.of(site.entity, kind, slots)
        return Change(
            entity=site.entity,
            id=site.id,
            subentity=site.subentity,
            target=change.path,
            kind=change.kind,
            grade=grade.name,
            pointers=tuple(f"/{slot}" for slot in slots),
            summary=self._summary(site, change.kind, slots),
        )

    @cached_property
    def routes(self) -> tuple[Route, ...]:
        """Every path shape the corpus can produce, compiled from the specs themselves."""
        found: list[Route] = []
        for entity in INSTANCED:
            if (spec := self.claims.spec(entity)) is None or spec.flat is None:
                continue
            found.append(Route(self._compile(spec.flat.path), entity))
            if spec.references.dir:
                shape = f"{Path(spec.flat.path).parent}/{spec.references.dir}/{{file}}"
                found.append(Route(self._compile(shape), entity, slotted=True))
        if persona := self.claims.find("persona", "documents"):
            found += [Route(self._compile(doc.target), Entity.PERSONA) for doc in persona.documents]
        if (cfg := self.claims.find("config", "config")) and cfg.config:
            found += [Route(self._compile(file.out), Entity.CONFIG, slot=file.slot) for file in cfg.config.files]
            found += [Route(self._compile(asset.out), Entity.CONFIG, slot=asset.slot) for asset in cfg.config.assets]
        return tuple(found)

    # --------------------------------------------------------------- private
    @staticmethod
    def _compile(shape: str) -> re.Pattern:
        """`skills/{id}/SKILL.md` → a pattern that names what it captured."""
        return re.compile(
            re.escape(shape).replace(r"\{id\}", r"(?P<id>[^/]+)").replace(r"\{file\}", r"(?P<file>[^/]+)")
        )

    def _slots(self, site: Site, kind: Kind, before: str, after: str) -> tuple[str, ...]:
        """Which slots of the entity moved between the two versions of this path."""
        if site.slot:
            return (site.slot,)
        return self.READERS[site.entity](self, site, before, after)

    def _frontmatter_slots(self, site: Site, before: str, after: str) -> tuple[str, ...]:
        """Every frontmatter key that appeared, vanished or changed, plus the body slot."""
        spec = self.claims.spec(site.entity)
        old, new = self._frontmatter(before), self._frontmatter(after)
        moved = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
        body = spec.flat.body_slot if spec and spec.flat and self._body(before) != self._body(after) else ""
        return tuple(sorted(moved | ({body} if body else set())))

    def _config_slots(self, site: Site, before: str, after: str) -> tuple[str, ...]:
        """Every top-level key of an emitted config file that moved."""
        old, new = self._json(before), self._json(after)
        return tuple(sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key)))

    def _persona_slots(self, site: Site, before: str, after: str) -> tuple[str, ...]:
        """A persona document is read back into its blocks; every slot of a block that moved, moved.

        The harness's regions are cut before reading: what it learns there is not a change of
        the corpus. A heading no block declares is the `unplaced` slot — never a neighbour's.
        """
        doc = self._documents[site.subentity]
        old, new = Typeset(doc).parse(before), Typeset(doc).parse(after)
        slots = {block.key: block.slots for block in doc.blocks}
        moved = (key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
        return tuple(sorted({slot for key in moved for slot in slots.get(key, [UNPLACED])}))

    @cached_property
    def _documents(self) -> Mapping[str, Document]:
        persona = self.claims.find("persona", "documents")
        return {doc.target: doc for doc in (persona.documents if persona else ())}

    #: How each entity's slots are read out of its flat form.
    READERS: Final[Mapping[Entity, Callable[..., tuple[str, ...]]]] = {
        Entity.SKILL: _frontmatter_slots,
        Entity.AGENT: _frontmatter_slots,
        Entity.COMMAND: _frontmatter_slots,
        Entity.WORKFLOW: _frontmatter_slots,  # body_slot names the graph: derived moves are `nodes` moves
        Entity.CONFIG: _config_slots,
        Entity.PERSONA: _persona_slots,
    }

    @staticmethod
    def _frontmatter(text: str) -> dict:
        found = FM_RE.search(text)
        return eserde.loads(found.group(1), format=eserde.Format.YAML) if found else {}

    @staticmethod
    def _body(text: str) -> str:
        return FM_RE.sub("", text, count=1).strip()

    @staticmethod
    def _json(text: str) -> dict:
        return eserde.loads(text, format=eserde.Format.JSONC) if text.strip() else {}

    @staticmethod
    def _summary(site: Site, kind: Kind, slots: tuple[str, ...]) -> str:
        """One short line a human reads without opening the diff."""
        what = site.subentity or site.id or site.entity.value
        verbs = {"added": "new", "removed": "gone", "changed": ", ".join(slots) or "no slot moved"}
        return f"{what}: {verbs[kind] if kind != 'changed' else verbs['changed']}"
