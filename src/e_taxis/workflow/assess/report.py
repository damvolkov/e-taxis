"""assess.report: the assessment as it stood after the adversary — radar/report.md, radar/assess.json, the state's index.

The verdict that stands is the verdict step's when the review stands, and the reviewer's own when it does not; the
report says which, and shows both. The index (`assessed.json` in the radar state dir, a map name → {verdict, date,
report}) is where radar-field's fit finds what was already judged: one row per name, the latest assessment winning."""

from typing import TYPE_CHECKING, Final

import anyio
import msgspec

from e_taxis.workflow.models.assess import (
    Assessed,
    Candidate,
    Health,
    Plan,
    Report,
    Review,
    Stats,
    Verdict,
)

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
INDEX: str = "assessed.json"
KPIS: Final[tuple[str, ...]] = (
    "last_release",
    "releases_per_year",
    "downloads_month",
    "dependents",
    "scorecard",
    "license",
    "open_issue_ratio",
    "contributors",
)


##### TYPES #####
class AssessReport:
    """Stateless: every part of the run comes in on each call."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _render_health(health: Health) -> str:
        values = msgspec.to_builtins(health)
        rows = "\n".join(
            f"| {kpi} | {'—' if values.get(kpi) is None else values[kpi]} | {health.sources.get(kpi, '—')} |"
            for kpi in KPIS
        )
        failed = "".join(f"\n- failed: {entry}" for entry in health.failed)
        notes = "".join(f"\n- {note}" for note in health.notes)
        return (
            f"Measured at {health.measured_at}.\n\n| KPI | Value | Source |\n|---|---|---|\n{rows}\n{failed}{notes}\n"
        )

    @staticmethod
    def _render_bench(plan: Plan, stats: Stats) -> str:
        direction = "higher is better" if stats.higher_is_better else "lower is better"
        arms = "\n".join(f"- `{arm.name}` ({arm.role}{f', {arm.version}' if arm.version else ''})" for arm in plan.arms)
        frame = (
            f"Hypothesis: {plan.hypothesis}\n\nPrimary metric **{stats.metric}** ({direction}), threshold "
            f"{stats.threshold:g}; cases {', '.join(plan.cases)}; n={plan.n}, warm-up {plan.warmup}, {plan.cache} "
            f"cache, seed {plan.seed}.\n\n{arms}\n"
        )
        match stats.mean:
            case None:
                return f"{frame}\n**{stats.outcome}** — {stats.reason}\n"
            case middle:
                secondary = "".join(f"\n- {name}: {said}" for name, said in stats.secondary.items())
                return (
                    f"{frame}\n{stats.candidate} - {stats.baseline}: mean {middle:.6g}, "
                    f"{stats.confidence:.0%} interval [{stats.low:.6g}, {stats.high:.6g}] over {stats.pairs} pairs "
                    f"({stats.resamples} paired-bootstrap resamples) → **{stats.outcome}**\n{secondary}\n"
                )

    @staticmethod
    def _render_verdict(report: Report) -> str:
        stood = (
            "the adversary let it stand"
            if report.stands
            else f"the adversary sank the proposed **{report.proposed}**: the reviewer's verdict stands"
        )
        evidence = "".join(f"\n- {line}" for line in report.evidence)
        objections = "".join(
            f"\n- {'refuted' if o.refuted else 'standing'}: {o.claim}{f' — {o.evidence}' if o.evidence else ''}"
            for o in report.objections
        )
        return (
            f"**{report.verdict}** — {stood}.\n\nLands in {report.landing}: `{report.command}`\n"
            f"\nEvidence:{evidence or ' none'}\n\nObjections:{objections or ' none'}\n"
        )

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def build(
        candidate: Candidate,
        *,
        plan: Plan,
        health: Health,
        stats: Stats,
        verdict: Verdict,
        review: Review,
        path: Path,
        date: str,
    ) -> Report:
        return Report(
            name=candidate.name,
            date=date,
            path=str(path),
            verdict=verdict.verdict if review.stands else review.verdict,
            proposed=verdict.verdict,
            stands=review.stands,
            landing=verdict.landing,
            command=verdict.command,
            candidate=candidate,
            incumbent=plan.incumbent,
            overlap=plan.overlap,
            health=health,
            stats=stats,
            evidence=verdict.evidence,
            objections=review.objections,
        )

    def render(self, report: Report, plan: Plan) -> str:
        """report.md: the verdict first, then what it stands on."""
        candidate = report.candidate
        where = " · ".join(
            part
            for part in (
                f"repo {candidate.repo}" if candidate.repo else "",
                f"{candidate.registry} {candidate.package}" if candidate.registry else "",
                f"topic {candidate.topic}" if candidate.topic else "",
            )
            if part
        )
        notes = "".join(f"\n- {note}" for note in candidate.notes)
        return (
            f"# radar-tech · {report.name} — {report.verdict}\n\n`{candidate.tech}` · {where or 'no source'} · "
            f"{report.date}\n{notes}\n\n## Verdict\n\n{self._render_verdict(report)}\n"
            f"## Against what we run\n\nIncumbent: {report.incumbent} · overlap: **{report.overlap}**\n\n"
            f"## Health\n\n{self._render_health(report.health)}\n"
            f"## Benchmark\n\n{self._render_bench(plan, report.stats)}"
        )

    @staticmethod
    async def record(state: Path, report: Report) -> Path:
        """The report's row in the state's index, written beside the others."""
        index = state / INDEX
        await anyio.Path(state).mkdir(parents=True, exist_ok=True)
        raw = await anyio.Path(index).read_bytes() if await anyio.Path(index).is_file() else b"{}"
        rows = msgspec.json.decode(raw, type=dict[str, Assessed])
        rows[report.name] = Assessed(verdict=report.verdict, date=report.date, report=report.path)
        await anyio.Path(index).write_bytes(msgspec.json.format(msgspec.json.encode(rows), indent=2))
        return index
