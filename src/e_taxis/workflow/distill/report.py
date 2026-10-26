"""distill.report: the run's answer — a short body to read first, then annexes for the detail.

**Harness** is e-nous; **blueprint** is e-arkhetypo. The body is one quick-view table per side and the project's own
drift; the annexes are YAML, one block per proposal, then what was not proposed, then the coverage of every plane.

The judge's verdicts and the adversary's reviews are joined to the graded candidates: a must or a should the adversary
brings down drops to the verdict it names; a candidate grade stopped is rejected with its reason and never becomes a
proposal, whatever a judge said of it. Each surviving proposal gets its `Handoff` mechanically from its targets — an
entity of the core goes to `emaintenance`, a place of the core that is no entity to `enhance` (W2), anything in
e-arkhetypo to a branch and a brief. `render` writes `report.md` without a model; `ship` lists the commands that apply
the musts. Every value in those commands is shell-quoted, and a proposal's text travels as its brief file, never inline."""

import shlex
from collections import Counter
from typing import TYPE_CHECKING, Final

import eserde
import msgspec

from e_taxis.workflow.models.distill import (
    BlueprintArea,
    BlueprintChange,
    BlueprintTarget,
    Candidate,
    Coverage,
    Emaintenance,
    Enhance,
    Fact,
    Grade,
    Handoff,
    HarnessKind,
    HarnessTarget,
    Judgement,
    Plane,
    Proposal,
    Report,
    Review,
    RunMeta,
    Target,
    Verdict,
    Waiver,
)
from e_taxis.workflow.models.entity import Entity

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
ORDER: Final[Mapping[Verdict, int]] = {Verdict.MUST: 0, Verdict.SHOULD: 1, Verdict.CASE: 2, Verdict.REJECT: 3}
HARNESS: str = "harness"
BLUEPRINT: str = "blueprint"
TITLE: int = 90
SECTIONS: Final[Mapping[object, str]] = {
    Entity.PERSONA: "persona",
    Entity.CONFIG: "config",
    HarnessKind.STACK: "stack",
    HarnessKind.SPEC: "specs",
    HarnessKind.MATRIX: "versioning",
    BlueprintArea.PROJECT: "projects",
    BlueprintArea.STACK: "stack",
    BlueprintArea.INFRA: "infra",
    BlueprintArea.TOOLS: "tools",
}

type Place = tuple[str, str, str, str]


##### TYPES #####
class DistillReport:
    """Builds, renders and ships the report of one run; `nous` is the e-nous checkout the apply commands run against."""

    __slots__ = ("_blueprint", "_nous")

    def __init__(self, *, blueprint: str, nous: str) -> None:
        self._blueprint = blueprint
        self._nous = nous

    ##### PRIVATE METHODS #####

    @staticmethod
    def _build_handoff(run: str, candidate: Candidate) -> Handoff:
        blueprint = tuple(t for t in candidate.targets if isinstance(t, BlueprintTarget))
        core = [t for t in candidate.targets if isinstance(t, HarnessTarget)]
        match (blueprint, core):
            case ((_, *_), _):
                return BlueprintChange(
                    targets=blueprint, branch=f"distill/{run}-{candidate.id}", brief=candidate.sketch
                )
            case ((), [HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity() as entity, id=ident, change=change), *_]):
                return Emaintenance(entity=entity, op=change, id=ident, details=candidate.sketch)
            case _:
                return Enhance(
                    entity=Entity.CONFIG, ids=tuple(t.name or t.kind.value for t in core), directive=candidate.sketch
                )

    @staticmethod
    def _build_dropped(
        judgements: tuple[Judgement, ...],
        final: Mapping[str, Verdict],
        reviewed: Mapping[str, Review],
        verdict: Verdict,
    ) -> tuple[Judgement, ...]:
        return tuple(
            Judgement(
                candidate=j.candidate,
                verdict=verdict,
                generality=j.generality,
                rationale=(reviewed[j.candidate].objection if j.candidate in reviewed else "") or j.rationale,
            )
            for j in judgements
            if final.get(j.candidate) is verdict
        )

    @staticmethod
    def _build_coverage(
        facts: tuple[Fact, ...],
        candidates: tuple[Candidate, ...],
        proposals: tuple[Proposal, ...],
        waivers: tuple[Waiver, ...],
    ) -> tuple[Coverage, ...]:
        """Per plane: facts found, candidates and proposals landing there, what the miners left and why, what nobody
        looked at."""
        answered = {f for c in candidates for f in c.facts}
        left = {w.fact: w for w in waivers if w.fact not in answered}
        landed = Counter(t.plane for c in candidates for t in {t.plane: t for t in c.targets}.values())
        kept = Counter(t.plane for p in proposals for t in {t.plane: t for t in p.candidate.targets}.values())
        return tuple(
            Coverage(
                plane=plane,
                facts=sum(1 for f in facts if f.plane is plane),
                candidates=landed[plane],
                proposals=kept[plane],
                open=tuple(f for f in facts if f.plane is plane and f.id not in answered and f.id not in left),
                waived=tuple((f, left[f.id].reason) for f in facts if f.plane is plane and f.id in left),
            )
            for plane in Plane
        )

    @staticmethod
    def _render_place(target: Target) -> Place:
        """(side, section, unit, layer): where a target sits."""
        match target:
            case HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity() as entity):
                return HARNESS, SECTIONS.get(entity, f"{entity}s"), target.id or "(new)", ""
            case HarnessTarget():
                return HARNESS, SECTIONS[target.kind], target.name or str(target.facet), ""
            case _:
                return BLUEPRINT, SECTIONS[target.area], target.unit, target.layer

    @staticmethod
    def _render_target(target: Target) -> str:
        match target:
            case HarnessTarget(kind=HarnessKind.ENTITY):
                part = f"{target.part} {target.name}".strip()
                return f"{target.change} · {target.entity} {target.id or '(new)'} · {part}"
            case HarnessTarget():
                return f"{target.change} · {target.kind} {target.name or target.facet}"
            case _:
                return (
                    f"{target.change} · {target.area} {target.unit}"
                    + (" (new)" if target.new else "")
                    + (f" · {target.layer}" if target.layer else "")
                    + (f" · {target.path}" if target.path else "")
                )

    @staticmethod
    def _render_title(candidate: Candidate) -> str:
        """The candidate's own title, or its sketch's first sentence cut to a line."""
        line = candidate.title or candidate.sketch.split(". ")[0].strip()
        return line if len(line) <= TITLE else line[: line.rfind(" ", 0, TITLE)] + "…"

    @staticmethod
    def _render_yaml(value: object) -> str:
        return (
            "```yaml\n"
            + eserde.dumps(msgspec.to_builtins(value), format=eserde.Format.YAML).decode().rstrip()
            + "\n```"
        )

    @staticmethod
    def _quick_units(places: list[Place]) -> str:
        """The units of a proposal's places, each with the layers it touches, in order of appearance."""
        units = dict.fromkeys(unit for _, _, unit, _ in places)
        layers = {
            unit: tuple(dict.fromkeys(layer for _, _, u, layer in places if u == unit and layer)) for unit in units
        }
        return ", ".join(f"{unit} ({', '.join(found)})" if found else unit for unit, found in layers.items())

    def _render_quick(self, report: Report, side: str) -> str:
        """One side's quick view: a row per proposal — its sections, its units with their layers — musts first."""
        rows = sorted(
            (
                (
                    ", ".join(dict.fromkeys(section for _, section, _, _ in places)),
                    ORDER[p.judgement.verdict],
                    self._quick_units(places),
                    p,
                )
                for p in report.proposals
                if (places := [place for t in p.candidate.targets if (place := self._render_place(t))[0] == side])
            ),
            key=lambda row: row[:3],
        )
        lines = [
            f"| {section} | {unit} | **{p.judgement.verdict}** | {self._render_title(p.candidate)} | "
            f"[{p.candidate.id}](#{p.candidate.id}) |"
            for section, _, unit, p in rows
        ]
        head = "| Section | Unit | Verdict | Proposal | Annex |\n|---|---|---|---|---|\n"
        return head + "\n".join(lines) if lines else "Nothing proposed here."

    def _render_card(self, report: Report, p: Proposal) -> str:
        card = {
            "id": p.candidate.id,
            "verdict": p.judgement.verdict,
            "generality": round(p.judgement.generality, 2),
            "title": self._render_title(p.candidate),
            "relation": p.candidate.relation,
            "replaces": list(p.candidate.replaces),
            "targets": [self._render_target(t) for t in p.candidate.targets],
            "propagated": list(p.grade.propagated),
            "matrix": p.grade.matrix or None,
            "reach": p.grade.reach,
            "recent_change": p.grade.duplicate_of or None,
            "claims": list(p.candidate.claims),
            "facts": list(p.candidate.facts),
            "proposal": p.candidate.sketch,
            "why": p.judgement.rationale,
            "adversary": (p.review.objection or "upheld") if p.review else None,
            "apply": self.command(p.handoff, self.brief(report, p.candidate.id)),
            "brief": self.brief(report, p.candidate.id),
        }
        return f"### {p.candidate.id}\n\n" + self._render_yaml({k: v for k, v in card.items() if v not in (None, [])})

    ############################################################

    ##### PUBLIC #####

    def command(self, handoff: Handoff, brief: str) -> str:
        """The command that applies a proposal: every value quoted; its text read from the brief file at run time."""
        said = f'"$(cat {shlex.quote(brief)})"'
        match handoff:
            case Emaintenance():
                fields = (f"entity={handoff.entity}", f"op={handoff.op}", f"id={handoff.id}")
                return (
                    f"taxis workflow run emaintenance --nous {shlex.quote(self._nous)} "
                    f"{' '.join(map(shlex.quote, fields))} details={said}"
                )
            case Enhance():
                ids = " ".join(map(shlex.quote, handoff.ids))
                return f"taxis enhance run {handoff.entity} {ids} --nous {shlex.quote(self._nous)} --directive {said}"
            case _:
                return f"git -C {shlex.quote(self._blueprint)} switch -c {shlex.quote(handoff.branch)}"

    def build(
        self,
        run: RunMeta,
        *,
        candidates: tuple[Candidate, ...],
        grades: tuple[Grade, ...],
        judgements: tuple[Judgement, ...],
        reviews: tuple[Review, ...],
        facts: tuple[Fact, ...] = (),
        waivers: tuple[Waiver, ...] = (),
        stale: tuple[Fact, ...] = (),
    ) -> Report:
        by_id = {c.id: c for c in candidates}
        graded = {g.candidate: g for g in grades if not g.stop}
        reviewed = {r.candidate: r for r in reviews}
        stopped = tuple(
            Judgement(
                candidate=g.candidate, verdict=Verdict.REJECT, generality=0.0, rationale="stopped: " + "; ".join(g.stop)
            )
            for g in grades
            if g.stop
        )
        final = {
            j.candidate: (
                reviewed[j.candidate].final
                if j.candidate in reviewed and not reviewed[j.candidate].upheld
                else j.verdict
            )
            for j in judgements
            if j.candidate in by_id and j.candidate in graded
        }
        kept = sorted(
            (j for j in judgements if final.get(j.candidate) in {Verdict.MUST, Verdict.SHOULD}),
            key=lambda j: (ORDER[final[j.candidate]], -j.generality),
        )
        proposals = tuple(
            Proposal(
                candidate=by_id[j.candidate],
                grade=graded[j.candidate],
                judgement=Judgement(
                    candidate=j.candidate, verdict=final[j.candidate], generality=j.generality, rationale=j.rationale
                ),
                review=reviewed.get(j.candidate),
                handoff=self._build_handoff(run.id, by_id[j.candidate]),
            )
            for j in kept
        )
        return Report(
            run=run,
            proposals=proposals,
            cases=self._build_dropped(judgements, final, reviewed, Verdict.CASE),
            rejected=(*self._build_dropped(judgements, final, reviewed, Verdict.REJECT), *stopped),
            candidates=candidates,
            coverage=self._build_coverage(facts, candidates, proposals, waivers),
            stale=stale,
        )

    @staticmethod
    def brief(report: Report, candidate: str) -> str:
        """Where a proposal's brief lives: the text its apply command reads."""
        return f"{report.run.folder}/briefs/{candidate}.md"

    def briefs(self, report: Report) -> dict[str, str]:
        """Every proposal's brief, by path: the sketch and the evidence it rests on."""
        return {
            self.brief(report, p.candidate.id): "\n\n".join(
                [
                    p.candidate.sketch,
                    "Evidence:\n" + "\n".join(f"- {msgspec.json.encode(e).decode()}" for e in p.candidate.evidence),
                ]
            )
            + "\n"
            for p in report.proposals
        }

    def render(self, report: Report) -> str:
        """A short body to read first — the quick view of each side and the project's drift — then the annexes."""
        run = report.run
        titles = {c.id: self._render_title(c) for c in report.candidates}
        sides = {p.candidate.id: {self._render_place(t)[0] for t in p.candidate.targets} for p in report.proposals}
        count = Counter(side for found in sides.values() for side in found)
        head = "\n\n".join(
            [
                f"# reverse-distill · {run.project.rsplit('/', 1)[-1]}",
                (
                    f"Run `{run.id}` · `{', '.join(run.branches)}` since `{run.base[:7]}` · harness "
                    f"`{run.harness[:7] or '?'}` · blueprint `{run.blueprint[:7] or '?'}` · **nothing here is applied**"
                ),
                *([f"> {' '.join(run.work.split())}"] if run.work else []),
                (
                    f"**{len(report.proposals)} proposals** — harness {count[HARNESS]} · blueprint {count[BLUEPRINT]} · "
                    f"{len(report.cases)} kept as this project's case · {len(report.rejected)} rejected · "
                    f"{len(report.stale)} drifts in the project"
                ),
            ]
        )
        drift = (
            "| Drift | What |\n|---|---|\n"
            + "\n".join(f"| `{f.id}` | {f.direction or f.status}: {f.detail} |" for f in report.stale)
            if report.stale
            else "None."
        )
        not_proposed = [
            {"id": j.candidate, "verdict": j.verdict, "title": titles.get(j.candidate, ""), "why": j.rationale}
            for j in (*report.cases, *report.rejected)
        ]
        coverage = (
            "| Plane | Facts | Candidates | Proposals | Waived | Open |\n|---|---:|---:|---:|---:|---:|\n"
            + "\n".join(
                f"| {c.plane} | {c.facts} | {c.candidates} | {c.proposals} | {len(c.waived)} | {len(c.open)} |"
                for c in report.coverage
            )
        )
        facts = {
            "waived": {str(c.plane): {f.id: why for f, why in c.waived} for c in report.coverage if c.waived},
            "open": {str(c.plane): {f.id: f.detail for f in c.open} for c in report.coverage if c.open},
        }
        cards = {
            side: [self._render_card(report, p) for p in report.proposals if side in sides[p.candidate.id]]
            for side in (HARNESS, BLUEPRINT)
        }
        parts = [
            head,
            "## Harness — e-nous\n\n" + self._render_quick(report, HARNESS),
            "## Blueprint — e-arkhetypo\n\n" + self._render_quick(report, BLUEPRINT),
            "## The project's own drift\n\nBehind its blueprint: to fix in the project, nothing to learn.\n\n" + drift,
            "---\n\n## Annex A — harness proposals\n\n" + ("\n\n".join(cards[HARNESS]) or "None."),
            "## Annex B — blueprint proposals\n\n" + ("\n\n".join(cards[BLUEPRINT]) or "None."),
            "## Annex C — not proposed\n\nThis project's own cases, and what was rejected or stopped.\n\n"
            + (self._render_yaml(not_proposed) if not_proposed else "None."),
            "## Annex D — coverage\n\nEvery plane looked at: facts found without a model, candidates, survivors, what"
            " the miners waived (with why) and what nobody looked at.\n\n"
            + coverage
            + "\n\n"
            + self._render_yaml(facts),
        ]
        return "\n\n".join(parts) + "\n"

    def ship(self, report: Report) -> tuple[str, ...]:
        """The commands that apply the musts whose handoff is an existing workflow; shoulds stay for the human."""
        return tuple(
            self.command(p.handoff, self.brief(report, p.candidate.id))
            for p in report.proposals
            if p.judgement.verdict is Verdict.MUST and isinstance(p.handoff, Emaintenance)
        )
