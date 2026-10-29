"""compare.report: the comparison as it stood — one row per incumbent, its rivals scored, what the bench and the adversary
left, the migration and where it lands.

An incumbent the rank kept never reached a bench: `keep`, by the rubric, with the reason. A benched one stands as its
ruling said when the adversary's review stands, as the reviewer's decision when it does not — `proposed` keeps the
ruling's own. `record` folds every verdict into the state's `compared.json` (incumbent → the latest)."""

from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.workflow.models.compare import Compared, Decision, Report, Ruling, Settled

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.models.compare import (
        Challenge,
        Contest,
        PairStats,
        Plans,
        Reviews,
        Shortlist,
        Stack,
        Verdicts,
    )

##### DEFAULTS #####
INDEX: str = "compared.json"


##### TYPES #####
class CompareReport:
    """Builds, renders and records one comparison."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _build_one(
        contest: Contest,
        stack: Stack,
        ruling: Ruling | None,
        review: Challenge | None,
        pieces: tuple[Plans, PairStats],
    ) -> Settled:
        plans, stats = pieces
        declared = tuple(dep for dep in stack.dependencies if dep.name.lower() == contest.incumbent.lower())
        kept = Settled(
            incumbent=contest.incumbent,
            decision=Decision.KEEP,
            proposed=Decision.KEEP,
            stands=True,
            scores=contest.scores,
            declared=declared,
            reason=contest.reason,
        )
        match (contest.rival, ruling):
            case (str() as rival, Ruling() as found) if rival:
                pass
            case _:
                return kept
        stands = review.stands if review else True
        plan = next((pair for pair in plans.pairs if (pair.incumbent, pair.rival) == (contest.incumbent, rival)), None)
        measured = next(
            (pair.stats for pair in stats.pairs if (pair.incumbent, pair.rival) == (contest.incumbent, rival)), None
        )
        return msgspec.structs.replace(
            kept,
            decision=found.decision if stands or review is None else review.decision,
            proposed=found.decision,
            stands=stands,
            rival=rival,
            landing=found.landing,
            command=found.command,
            evidence=found.evidence,
            objections=review.objections if review else (),
            migration=plan.migration if plan else None,
            stats=measured,
        )

    @staticmethod
    def _render_one(settled: Settled) -> str:
        scores = "\n".join(
            f"| {score.name} | {score.total} | {', '.join(f'{k} {v}' for k, v in score.terms.items() if v)} "
            f"| {', '.join(score.unmeasured) or '—'} | {score.stars if score.stars is not None else '—'} |"
            for score in settled.scores
        )
        interval = (
            f"{settled.stats.outcome} [{settled.stats.low}, {settled.stats.high}]" if settled.stats else "not benched"
        )
        evidence = "\n".join(f"- {line}" for line in settled.evidence)
        objections = "\n".join(
            f"- {'refuted' if item.refuted else 'standing'}: {item.claim}" for item in settled.objections
        )
        migration = (
            "\n".join(
                [
                    *(f"- file: {file}" for file in settled.migration.files),
                    *(f"- change: {change}" for change in settled.migration.changes),
                ]
            )
            if settled.migration
            else ""
        )
        stood = "the adversary let it stand" if settled.stands else f"the adversary sank {settled.proposed}"
        parts = [
            f"## {settled.incumbent} — {settled.decision}",
            f"{settled.rival and f'against **{settled.rival}** · '}{stood} · bench: {interval}",
            settled.reason,
            f"| subject | score | terms | unmeasured | stars |\n|---|---:|---|---|---:|\n{scores}",
            *([f"Evidence:\n{evidence}"] if evidence else []),
            *([f"Objections:\n{objections}"] if objections else []),
            *([f"Migration:\n{migration}"] if migration else []),
            *([f"Lands in {settled.landing}: `{settled.command}`"] if settled.command else []),
        ]
        return "\n\n".join(parts)

    ############################################################

    ##### PUBLIC #####

    def build(
        self,
        stack: Stack,
        shortlist: Shortlist,
        answers: tuple[Plans, PairStats, Verdicts, Reviews],
        *,
        date: str,
        path: str,
    ) -> Report:
        plans, stats, verdicts, reviews = answers
        rulings = {ruling.incumbent: ruling for ruling in verdicts.verdicts}
        challenges = {review.incumbent: review for review in reviews.reviews}
        return Report(
            project=stack.project,
            query=stack.query,
            date=date,
            path=path,
            settled=tuple(
                self._build_one(
                    contest, stack, rulings.get(contest.incumbent), challenges.get(contest.incumbent), (plans, stats)
                )
                for contest in shortlist.contests
            ),
        )

    def render(self, report: Report) -> str:
        rows = "\n".join(
            f"| {item.incumbent} | {item.rival or '—'} | **{item.decision}** | {item.reason} |"
            for item in report.settled
        )
        head = (
            f"# radar-stack · {report.project}\n\n> {report.query}\n\n{report.date}\n\n"
            f"| incumbent | rival | verdict | why |\n|---|---|---|---|\n{rows}"
        )
        return "\n\n".join([head, *(self._render_one(item) for item in report.settled)]) + "\n"

    @staticmethod
    async def record(state: Path, report: Report) -> Path:
        """`compared.json` with this report's verdicts folded in, incumbent → the latest."""
        index = anyio.Path(state / INDEX)
        await anyio.Path(state).mkdir(parents=True, exist_ok=True)
        known = msgspec.json.decode(await index.read_bytes(), type=dict[str, Compared]) if await index.exists() else {}
        rows = {
            item.incumbent: Compared(verdict=item.decision, date=report.date, report=report.path)
            for item in report.settled
        }
        await index.write_bytes(msgspec.json.format(msgspec.json.encode(known | rows)))
        return state / INDEX
