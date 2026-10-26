"""distill.grade: the deterministic weight of every candidate the miners proposed, before any model judges it.

The candidates are read back from the miners' answers through the `Candidate` model and merged by what they touch.
A contradiction is then propagated: every term it `replaces` is grepped (word, case-insensitive) across the harness
scope (`core/`, `specs/tekton/`), and every place that still states it becomes a target — a typed one when the path
is a known part of an entity, evidence in any case — so no place keeps the old fact; a term the core never states is
a contradiction of nothing, and stops the candidate. Each candidate then gets a `Grade`: the versioning matrix's
verdict on the slots it changes, whether every target exists (or is created on purpose), its reach, and the latest
commit on the same place (a duplicate to look at). An incoherent candidate or target, a place the matrix does not
judge, an update of something missing or a create of something present stops the candidate here: no model weighs
what cannot land."""

import re
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

import msgspec

from e_taxis.workflow.models.distill import (
    BlueprintTarget,
    Candidate,
    Change,
    CodeEvidence,
    Grade,
    HarnessFacet,
    HarnessKind,
    HarnessPart,
    HarnessTarget,
    Propagation,
    Relation,
    Target,
)
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import CommandError, DistillError, UnknownSlotError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.workflow.distill.matrix import Kind, VersionMatrix
    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
### the matrix slot a part of an entity's anatomy is; a persona slot is graded by its own name.
SLOT: Final[Mapping[tuple[Entity, HarnessPart], str]] = {
    (Entity.SKILL, HarnessPart.MANIFEST): "description",
    (Entity.SKILL, HarnessPart.INSTRUCTIONS): "instructions",
    (Entity.SKILL, HarnessPart.REFERENCE): "references/x.md",
    (Entity.SKILL, HarnessPart.LIB): "references/lib.md",
    (Entity.AGENT, HarnessPart.MANIFEST): "permission",
    (Entity.AGENT, HarnessPart.PROMPT): "prompt",
    (Entity.COMMAND, HarnessPart.MANIFEST): "arguments",
    (Entity.COMMAND, HarnessPart.TEMPLATE): "template",
    (Entity.WORKFLOW, HarnessPart.MANIFEST): "parameters",
    (Entity.WORKFLOW, HarnessPart.NODE): "nodes",
}
### the file a part is inside its entity's folder; `lib` before `reference`, so lib.md reads as the library.
FILES: Final[Mapping[tuple[Entity, HarnessPart], str]] = {
    (Entity.SKILL, HarnessPart.MANIFEST): "skill.yaml",
    (Entity.SKILL, HarnessPart.INSTRUCTIONS): "instructions.md",
    (Entity.SKILL, HarnessPart.LIB): "references/lib.md",
    (Entity.SKILL, HarnessPart.REFERENCE): "references/{name}.md",
    (Entity.AGENT, HarnessPart.MANIFEST): "agent.yaml",
    (Entity.AGENT, HarnessPart.PROMPT): "prompt.md",
    (Entity.COMMAND, HarnessPart.MANIFEST): "command.yaml",
    (Entity.COMMAND, HarnessPart.TEMPLATE): "template.md",
    (Entity.WORKFLOW, HarnessPart.MANIFEST): "workflow.yaml",
    (Entity.WORKFLOW, HarnessPart.NODE): "nodes/{name}.yaml",
}
KIND: Final[Mapping[Change, Kind]] = {Change.CREATE: "added", Change.RETIRE: "removed", Change.UPDATE: "changed"}
GIT: float = 60.0
NONE: int = 1


##### TYPES #####
class DistillGrade:
    """Weighs candidates against the matrix and the two trees. `layout` is where each entity's instances live in e-nous
    (from its schema); `scope` the e-nous folders doctrine lives in; `ref` the e-arkhetypo tree weighed (empty: the
    checkout)."""

    __slots__ = ("_blueprint", "_command", "_harness", "_layout", "_matrix", "_published", "_ref", "_scope")

    def __init__(
        self,
        command: CommandPort,
        matrix: VersionMatrix,
        *,
        harness: Path,
        blueprint: Path,
        layout: Mapping[Entity, Path],
        scope: tuple[str, ...],
        ref: str = "",
    ) -> None:
        self._command = command
        self._matrix = matrix
        self._harness = harness
        self._blueprint = blueprint.expanduser()
        self._layout = layout
        self._scope = scope
        self._ref = ref
        self._published: frozenset[str] = frozenset()

    ##### PRIVATE METHODS #####

    async def _common_git(self, repo: Path, *args: str) -> str:
        return await self._command.run("git", "-C", str(repo), *args, limit=GIT)

    def _grade_where(self, target: Target) -> tuple[Path, Path]:  # noqa: PLR0911 — one arm per kind of place
        """The repo a target lives in, and the folder or file it names there."""
        match target:
            case HarnessTarget(kind=HarnessKind.STACK, facet=facet):
                return self._harness, Path("core", facet, "stack.yaml")
            case HarnessTarget(kind=HarnessKind.MATRIX):
                return self._harness, Path("core/versioning/matrix.yaml")
            case HarnessTarget(kind=HarnessKind.SPEC, name=name):
                return self._harness, Path("specs", name)
            case HarnessTarget(entity=Entity.PERSONA, facet=facet):
                return self._harness, Path("core", facet, "persona")
            case HarnessTarget(entity=Entity.CONFIG, facet=facet, name=name):
                return self._harness, Path("core", facet, "config", f"{name}.yaml")
            case HarnessTarget(entity=Entity() as entity, id=ident, part=part, name=name):
                ### a reference named as its path (`references/x.md`) is the same place as its bare name (`x`).
                bare = PurePosixPath(name).stem
                return self._harness, self._layout[entity] / ident / FILES.get((entity, part), "").format(name=bare)
            case BlueprintTarget(path=path) if path:
                return self._blueprint, Path(path)
            case BlueprintTarget():
                return self._blueprint, Path(target.root)
            case _:
                return self._harness, Path()

    def _grade_matrix(self, target: Target) -> tuple[str, str]:
        """The matrix's grade of what the target changes, or why the matrix cannot judge it."""
        match target:
            case HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity() as entity):
                slot = target.name if entity is Entity.PERSONA else SLOT.get((entity, target.part), "")
                try:
                    return self._matrix.of(entity, KIND[target.change], (slot,) if slot else ()).name, ""
                except UnknownSlotError as unjudged:
                    return "", f"the matrix does not judge {unjudged.message}"
            case _:
                return "", ""

    def _grade_present(self, repo: Path, place: Path) -> bool:
        """Whether a place exists: on disk for e-nous, in the weighed tree for e-arkhetypo."""
        return str(place) in self._published if repo == self._blueprint and self._ref else (repo / place).exists()

    @staticmethod
    def _recent_commits(said: str) -> list[list[str]]:
        return [block.strip().splitlines() for block in re.split(r"\n(?=[0-9a-f]{7,} )", said.strip()) if block]

    @staticmethod
    def _recent_touches(row: str, spot: str) -> bool:
        """Whether a `--name-status` row changed `spot` (a pure move or rename is no change)."""
        return not row.startswith("R100") and any(
            col == spot or col.startswith(spot + "/") for col in row.split("\t")[1:]
        )

    async def _grade_recent(self, repo: Path, place: Path) -> str:
        """The latest commit of the last 30 days that changed the same place."""
        rev = self._ref if repo == self._blueprint and self._ref else "HEAD"
        try:
            said = await self._common_git(
                repo,
                "log",
                rev,
                "--since=30.days",
                "-M",
                "--full-diff",
                "--format=%h %s",
                "--name-status",
                "--",
                str(place),
            )
        except CommandError:
            return ""
        return next(
            (
                lines[0]
                for lines in self._recent_commits(said)
                if any(self._recent_touches(row, str(place)) for row in lines[1:])
            ),
            "",
        )

    async def _grade_one(self, candidate: Candidate, spread: Propagation) -> Grade:
        places = [self._grade_where(target) for target in candidate.targets]
        sited = list(zip(candidate.targets, places, strict=True))
        graded = [self._grade_matrix(target) for target in candidate.targets]
        stop = [
            *candidate.problems(),
            *(problem for target in candidate.targets for problem in target.problems()),
            *(
                f"{place} does not exist"
                for target, (repo, place) in sited
                if target.change is not Change.CREATE
                and not self._grade_present(repo, place)
                and not (isinstance(target, BlueprintTarget) and target.new)
            ),
            *(
                f"{place} already exists"
                for target, (repo, place) in sited
                if target.change is Change.CREATE and self._grade_present(repo, place)
            ),
            *(why for _, why in graded if why),
            *(
                f"`{term}` appears nowhere in {', '.join(self._scope)}: the core does not state what this contradicts"
                for term in spread.silent
            ),
        ]
        weights = [name for name, _ in graded if name]
        recent = [await self._grade_recent(repo, place) for repo, place in places]
        return Grade(
            candidate=candidate.id,
            matrix=max(weights, key=lambda name: self._matrix[name].level, default=""),
            reach=candidate.reach,
            exists=all(self._grade_present(repo, place) for repo, place in places),
            duplicate_of=next((r for r in recent if r), ""),
            stop=tuple(stop),
            propagated=spread.added,
        )

    @staticmethod
    def _propagate_within(path: PurePosixPath, folder: Path) -> tuple[str, ...]:
        return path.parts[len(folder.parts) :] if path.parts[: len(folder.parts)] == folder.parts else ()

    @staticmethod
    def _propagate_part(entity: Entity, rest: str) -> tuple[HarnessPart, str] | None:
        """The part of `entity` a file inside its folder is, and the part's name; None for a file no part owns."""
        return next(
            (
                (part, found.groupdict().get("name") or "")
                for (owner, part), pattern in FILES.items()
                if owner is entity
                and (found := re.fullmatch(re.escape(pattern).replace(r"\{name\}", r"(?P<name>[^/]+)"), rest))
            ),
            None,
        )

    def _propagate_target(self, path: str) -> HarnessTarget | None:
        """The typed place a harness file is, when it is one; None leaves it as evidence alone."""
        place = PurePosixPath(path)
        owned = next(
            (
                (entity, rest)
                for entity, folder in self._layout.items()
                if len(rest := self._propagate_within(place, folder)) > 1
            ),
            None,
        )
        match (owned, place.parts):
            case ((Entity() as entity, (ident, *tail)), _) if part := self._propagate_part(entity, "/".join(tail)):
                return HarnessTarget(entity=entity, id=ident, part=part[0], name=part[1])
            case (None, ("specs", *rest)):
                return HarnessTarget(kind=HarnessKind.SPEC, name="/".join(rest))
            case (None, ("core", str() as facet, "stack.yaml")) if facet in HarnessFacet:
                return HarnessTarget(kind=HarnessKind.STACK, facet=HarnessFacet(facet))
            case (None, ("core", str() as facet, "config", module)) if facet in HarnessFacet:
                return HarnessTarget(
                    facet=HarnessFacet(facet),
                    entity=Entity.CONFIG,
                    id=Entity.CONFIG.value,
                    part=HarnessPart.MODULE,
                    name=PurePosixPath(module).stem,
                )
            case _:
                return None

    async def _propagate_hits(self, term: str) -> tuple[tuple[str, int], ...]:
        """Every (path, line) of the harness scope that states `term` as a word, case-insensitive."""
        try:
            said = await self._common_git(
                self._harness, "grep", "--untracked", "-n", "-I", "-i", "-w", "-F", "-e", term, "--", *self._scope
            )
        except CommandError as failed:
            match failed.code:
                case 1:
                    return ()
                case _:
                    msg = f"cannot grep {self._harness} for {term!r}: {failed.message}"
                    raise DistillError(msg) from failed
        return tuple((path, int(line)) for row in said.splitlines() for path, line, _ in (row.split(":", 2),))

    async def _propagate_one(self, candidate: Candidate) -> tuple[Candidate, Propagation]:
        """The candidate with every place that still states what it replaces added; what it added, what grepped nothing."""
        terms = tuple(term.strip() for term in candidate.replaces if term.strip())
        hits = {term: await self._propagate_hits(term) for term in terms}
        known = {self._grade_where(target) for target in candidate.targets}
        typed = {
            self._grade_where(target): target
            for path, _ in sorted({hit for found in hits.values() for hit in found})
            if (target := self._propagate_target(path))
        }
        fresh = {place: target for place, target in typed.items() if place not in known}
        evidence = tuple(
            CodeEvidence(path=path, lines=(line, line), symbol=term)
            for term, found in hits.items()
            for path, line in found
        )
        amended = msgspec.structs.replace(
            candidate, targets=(*candidate.targets, *fresh.values()), evidence=(*candidate.evidence, *evidence)
        )
        return amended, Propagation(
            added=tuple(str(place) for _, place in fresh),
            silent=tuple(term for term, found in hits.items() if not found),
        )

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def merge(*sides: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
        """Both miners' candidates, one per set of targets: what lands on the same place is folded into the first.

        Ids are the miners' own, so sketches that cite each other still read; a clash gets a suffix."""
        flat = [candidate for candidates in sides for candidate in candidates]
        keys = [tuple(sorted(repr(target) for target in candidate.targets)) for candidate in flat]
        folded = {key: [c for c, k in zip(flat, keys, strict=True) if k == key] for key in dict.fromkeys(keys)}
        heads = [group[0].id for group in folded.values()]
        ids = [ident if heads.count(ident) == 1 else f"{ident}-{n}" for n, ident in enumerate(heads, start=1)]
        return tuple(
            msgspec.structs.replace(
                group[0],
                id=ident,
                claims=tuple(dict.fromkeys(k for c in group for k in c.claims)),
                facts=tuple(dict.fromkeys(f for c in group for f in c.facts)),
                replaces=tuple(dict.fromkeys(t for c in group for t in c.replaces)),
                sketch="\n\n".join(f"({c.id}) {c.sketch}" if len(group) > 1 else c.sketch for c in group),
                evidence=tuple(e for c in group for e in c.evidence),
            )
            for ident, group in zip(ids, folded.values(), strict=True)
        )

    async def propagate(
        self, candidates: tuple[Candidate, ...]
    ) -> tuple[tuple[Candidate, ...], dict[str, Propagation]]:
        """Every contradiction reaching every place that still states what it replaces; what each one did, by id."""
        done = [
            await self._propagate_one(candidate)
            if candidate.relation is Relation.CONTRADICTS
            else (candidate, Propagation())
            for candidate in candidates
        ]
        return tuple(candidate for candidate, _ in done), {candidate.id: spread for candidate, spread in done}

    async def grade(
        self,
        candidates: tuple[Candidate, ...],
        over: frozenset[str] = frozenset(),
        spread: Mapping[str, Propagation] | None = None,
    ) -> tuple[Grade, ...]:
        """Every candidate weighed; one in `over` (past its miner's cap) is stopped and says so, never dropped."""
        listing = (
            await self._common_git(self._blueprint, "ls-tree", "-r", "--name-only", self._ref) if self._ref else ""
        ).splitlines()
        self._published = frozenset(
            {*listing, *(str(parent) for path in listing for parent in Path(path).parents if str(parent) != ".")}
        )
        graded = [
            await self._grade_one(candidate, (spread or {}).get(candidate.id, Propagation()))
            for candidate in candidates
        ]
        return tuple(
            msgspec.structs.replace(g, stop=(*g.stop, "past its miner's cap")) if g.candidate in over else g
            for g in graded
        )
