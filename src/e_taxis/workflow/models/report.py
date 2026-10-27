"""models.report: a plane run, concluded — rebuilt from its ledger alone, rendered for a human or a machine.

The ledger is the truth; this is its fold. An evaluation concludes `needs` per subject (the enhancer's input), an
enhancement one `Verdict` per subject (what `enhance promote` may apply). Every row reads its evidence in one line
from the metrics it carries."""

from collections import Counter
from pathlib import PurePosixPath

from msgspec import Struct

from e_taxis.workflow.models.metrics import DecisionMetrics, Need, NeedsMetrics, PatchMetrics
from e_taxis.workflow.models.plane import PlaneManifest
from e_taxis.workflow.models.run import NodeRun, Status
from e_taxis.workflow.models.verdict import Decision, Verdict

##### DEFAULTS #####
NEEDS: str = "needs"
DECIDE: str = "decide"
PATCH: str = "patch"


##### TYPES #####
class PlaneReport(Struct, frozen=True, kw_only=True):
    """A run's manifest and every node run it recorded; `folder` is where it lives."""

    manifest: PlaneManifest
    runs: tuple[NodeRun, ...]
    folder: str

    ##### PRIVATE METHODS #####

    def _latest(self, node: str, subject: str) -> NodeRun | None:
        return next((run for run in reversed(self.runs) if run.node == node and run.subject == subject), None)

    def _verdict(self, subject: str) -> Verdict | None:
        match (self._latest(DECIDE, subject), self._latest(PATCH, subject)):
            case (NodeRun(metrics=DecisionMetrics() as verdict), patch):
                return Verdict(
                    subject=subject,
                    decision=Decision(verdict.decision),
                    reasons=verdict.reasons,
                    grade=verdict.grade,
                    bump=verdict.bump,
                    patch=patch.metrics.path if patch and isinstance(patch.metrics, PatchMetrics) else "",
                    evidence=tuple(f"{run.node}:{run.status}" for run in self.runs if run.subject == subject),
                )
            case _:
                return None

    ############################################################

    ##### PUBLIC #####

    @staticmethod
    def row(run: NodeRun) -> str:
        """One node run as a report line: node, status, seconds, cost, its evidence, why."""
        detail = getattr(run.metrics, "summary", "")
        why = f" — {run.reason}" if run.reason else ""
        cost = f" · {run.tokens} tok" if run.tokens else ""
        return f"  {run.node:<22}{run.status:<8}{run.seconds:>6.1f}s{cost}  {detail}{why}"

    @property
    def needs(self) -> dict[str, tuple[Need, ...]]:
        return {
            subject: run.metrics.needs
            for subject in self.manifest.subjects
            if (run := self._latest(NEEDS, subject)) and isinstance(run.metrics, NeedsMetrics)
        }

    @property
    def verdicts(self) -> tuple[Verdict, ...]:
        return tuple(verdict for subject in self.manifest.subjects if (verdict := self._verdict(subject)))

    @property
    def errored(self) -> tuple[NodeRun, ...]:
        """The node runs that broke: the only thing that makes a plane run fail (a red gate is a reading)."""
        return tuple(run for run in self.runs if run.status is Status.ERROR)

    @property
    def totals(self) -> str:
        counted = Counter(run.status.value for run in self.runs)
        tokens = sum(run.tokens for run in self.runs)
        return " · ".join(f"{status} {count}" for status, count in sorted(counted.items())) + f" · {tokens} tokens"

    @property
    def markdown(self) -> str:
        man = self.manifest
        origin = " · ".join(
            part
            for part in (
                f"from `{man.source}`" if man.source else "",
                f"candidate of `{man.candidate}` (patched: {', '.join(man.patched) or 'none'})"
                if man.candidate
                else "",
                f"directive: {man.directive}" if man.directive else "",
                "manual edits" if man.manual else "",
            )
            if part
        )
        needs = [f"| {s} | {len(n)} | {', '.join(sorted({x.kind for x in n})) or '—'} |" for s, n in self.needs.items()]
        verdicts = [
            f"| {v.subject} | **{v.decision}** | {v.grade or '—'} | {v.bump or '—'} | "
            f"{f'`{PurePosixPath(v.patch).name}`' if v.patch else '—'} |"
            for v in self.verdicts
        ]
        corpus = ["## corpus", "", "```", *(self.row(run) for run in self.runs if not run.subject), "```", ""]
        subjects = [
            line
            for s in man.subjects
            for line in (f"## {s}", "", "```", *(self.row(run) for run in self.runs if run.subject == s), "```", "")
        ]
        where = f"e-nous `{man.nous}` @ `{man.base_sha[:10]}` · tree `{man.tree}` · {man.backend}"
        verdict = ["## Verdicts", "", "| subject | decision | grade | bump | patch |", "|---|---|---|---|---|"]
        return "\n".join(
            [
                f"# {man.plane} {man.target} · {man.run_id}",
                "",
                f"{where} · cadence {man.cadence} · {len(man.subjects)} subjects",
                "",
                *([origin, ""] if origin else []),
                f"**{self.totals}**",
                "",
                *(["## Needs", "", "| subject | needs | kinds |", "|---|---|---|", *needs, ""] if needs else []),
                *([*verdict, *verdicts, ""] if verdicts else []),
                *corpus,
                *subjects,
            ]
        )
