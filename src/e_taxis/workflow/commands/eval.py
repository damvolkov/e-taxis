"""commands.eval: driving adapter of the evaluator — `taxis eval run | graph | needs`.

`run` measures a target's subjects in an e-nous checkout, read-only toward it: the live rows on stderr as each node
lands, the subjects' needs and the report's path on stdout; it fails (24) only when a node broke — a red gate is a
reading, not a failure. `--candidate RUN|latest` measures an enhancer run's candidate instead of the checkout as it
stands. `graph` prints the evaluator's graphs (e-taxis's own: no checkout read). `needs` prints an evaluation's open
needs, of one owner when named, and exits 1 while any is open — what a bounded loop's `until` check reads."""

import sys
from pathlib import Path

from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.workflow.models.error import NeedsOpenError, RunFailedError
from e_taxis.workflow.models.metrics import Owner
from e_taxis.workflow.models.plane import Cadence, Plane, Target
from e_taxis.workflow.models.report import PlaneReport
from e_taxis.workflow.models.run import NodeRun
from e_taxis.workflow.services.plane import PlaneRun

##### DEFAULTS #####
LATEST: str = "latest"


##### UTILITIES #####
def render_live(run: NodeRun) -> None:
    """One node run, the moment the ledger records it — on stderr, so stdout stays the result."""
    head = PlaneReport.row(run).splitlines()[0].strip()
    sys.stderr.write(f"  {run.subject or '·':<24}{head[:150]}\n")


def render_close(report: PlaneReport, console: Console) -> None:
    """What every plane run prints: its conclusions, its totals, where its report is; 24 when a node broke."""
    needs = [f"  {s:<24}{len(n)} needs  {', '.join(sorted({x.kind for x in n}))}" for s, n in report.needs.items()]
    verdicts = [
        f"  {v.subject:<24}{v.decision:<9}{v.grade or '—':<11}{'; '.join(v.reasons)[:110]}" for v in report.verdicts
    ]
    _ = [console.out(line, highlight=False) for line in (*needs, *verdicts)]
    console.out(f"[{report.manifest.plane}] {report.totals} → {report.folder}/report.md", highlight=False)
    match report.errored:
        case ():
            pass
        case broken:
            msg = f"{len(broken)} node run(s) broke: {', '.join(f'{r.node}/{r.subject or "·"}' for r in broken)}"
            raise RunFailedError(msg)


##### COMMANDS #####
async def run(
    target: Target,
    *ids: str,
    nous: Path,
    cadence: Cadence | None = None,
    candidate: str = "",
    keep: bool = False,
    only: str = "",
    runner: Inject[PlaneRun],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Evaluate TARGET (all its subjects, or the IDS named), read-only toward the checkout.

    Args:
        target: corpus · skill · agent · command · workflow · tool · persona · config · spec.
        ids: subjects to evaluate; all of the target's when omitted.
        nous: the e-nous checkout, read as it stands; its `.reports/` holds the run.
        cadence: commit · nightly · weekly · manual — which nodes are due (default: TAXIS_EVAL_CADENCE).
        candidate: an enhancer run id, or `latest`: measure that run's candidate (its base, its patches applied).
        keep: keep the run's clone (a candidate evaluation's) after the run.
        only: comma-separated measures to run (activation, effect, semantic…); the free gates always run.
    """
    report = await runner.evaluate(
        nous,
        target,
        ids,
        cadence or settings.taxis_eval_cadence,
        candidate=candidate,
        keep=keep,
        only=tuple(name for name in only.split(",") if name),
        notify=render_live,
    )
    render_close(report, console)


async def graph(target: Target | None = None, *, runner: Inject[PlaneRun], console: Inject[Console]) -> None:
    """Print the evaluator's graph of TARGET, or of every target, and prove each wired.

    Args:
        target: one target; all when omitted.
    """
    console.out(runner.describe(Plane.EVALUATOR, target), highlight=False)


async def needs(
    target: Target,
    *,
    nous: Path,
    run: str = LATEST,
    owner: Owner | None = None,
    runner: Inject[PlaneRun],
    console: Inject[Console],
) -> None:
    """Print the open needs of an evaluation of TARGET; exit 1 while any is open.

    Args:
        target: the evaluated target.
        nous: the e-nous checkout whose `.reports/` holds the run.
        run: an evaluator run id, or `latest` (the newest evaluation of TARGET).
        owner: agent · human — only the needs that owner acts on; all when omitted.
    """
    report = await runner.load(await runner.folder(nous, run, Plane.EVALUATOR, target))
    found = sorted(
        f"{subject:<24}{need.kind:<10}{need.detail}"
        for subject, items in report.needs.items()
        for need in items
        if owner is None or need.owner is owner
    )
    match found:
        case []:
            console.out(f"no open {f'{owner} ' if owner else ''}needs", highlight=False)
        case _:
            _ = [console.out(line, highlight=False) for line in found]
            msg = f"{len(found)} open need(s) in {report.manifest.run_id}"
            raise NeedsOpenError(msg)
