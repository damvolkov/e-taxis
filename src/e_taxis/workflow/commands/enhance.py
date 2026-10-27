"""commands.enhance: driving adapter of the enhancer — `taxis enhance run | graph | promote`.

`run` acts only on a reason (`--from` an evaluation, `--directive`, `--manual`), in a sandbox: verdicts and patches
under the run folder, the checkout untouched; exit 3 when no subject has a need, 28 when the reason is missing or a
subject has uncommitted edits it was not told to take. `promote` is a human command, on purpose: it needs a terminal
— or the mandate a terminal-started `taxis` hands its children (`TAXIS_HUMAN`), so a workflow you run yourself may
promote — and never runs inside a session an agent drives (`TAXIS_HEADLESS`, `OPS_GLOBAL__HEADLESS`), mandate or
not. It asks before writing unless `--yes`; a closed stdin is a no."""

import sys
from pathlib import Path
from typing import Annotated

import anyio
from cyclopts import Parameter
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.workflow.commands.eval import render_close, render_live
from e_taxis.workflow.models.error import HumanError, RefusedError
from e_taxis.workflow.models.metrics import Owner
from e_taxis.workflow.models.plane import Cadence, Plane, Target
from e_taxis.workflow.services.plane import PlaneRun
from e_taxis.workflow.services.promote import PlanePromote

##### DEFAULTS #####
LATEST: str = "latest"
YES: frozenset[str] = frozenset({"y", "yes"})


##### UTILITIES #####
def human_guard(settings: TaxisSettings, *, terminal: bool) -> None:
    """A human command needs a human: refused in an agent's session, and without a terminal or a mandate."""
    match (settings.taxis_headless, terminal or settings.taxis_human):
        case (True, _):
            msg = "promote: a session an agent drives never runs a human command"
            raise HumanError(msg)
        case (_, False):
            msg = "promote: no terminal — a human command needs someone at the keyboard (or a terminal's mandate)"
            raise HumanError(msg)
        case _:
            pass


async def human_confirm(question: str, *, yes: bool) -> bool:
    """`--yes` is the only silence; otherwise ask, default no; a closed stdin is a no."""
    match yes:
        case True:
            return True
        case _:
            try:
                said = await anyio.to_thread.run_sync(input, f"{question} [y/N] ")
            except EOFError:
                return False
            return said.strip().lower() in YES


##### COMMANDS #####
async def run(
    target: Target,
    *ids: str,
    nous: Path,
    source: Annotated[str, Parameter(name="--from")] = "",
    directive: str = "",
    manual: bool = False,
    owner: Owner | None = None,
    cadence: Cadence | None = None,
    keep: bool = False,
    runner: Inject[PlaneRun],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Enhance TARGET's subjects in a sandbox, on a reason, and write their verdicts and patches.

    Args:
        target: skill · agent · command · workflow · tool · persona · config · spec.
        ids: subjects to enhance; with --from and no ids, those the evaluation found needs for.
        nous: the e-nous checkout (read; never written — `promote` writes).
        source: [--from] an evaluator run id, or `latest` (the newest evaluation of TARGET).
        directive: your instruction, folded into the subject by the integrator (needs ids).
        manual: propose your working-tree edits of the subjects (measured base against candidate).
        owner: with --from and no ids, only the subjects with a need this owner acts on (agent · human).
        cadence: commit · nightly · weekly · manual — which nodes are due (default: TAXIS_EVAL_CADENCE).
        keep: keep the sandbox and the candidate trees after the run.
    """
    report = await runner.enhance(
        nous,
        target,
        ids,
        cadence or settings.taxis_eval_cadence,
        source=source,
        directive=directive,
        manual=manual,
        owner=owner,
        keep=keep,
        notify=render_live,
    )
    render_close(report, console)


async def graph(target: Target | None = None, *, runner: Inject[PlaneRun], console: Inject[Console]) -> None:
    """Print the enhancer's graph of TARGET, or of every target, and prove each wired.

    Args:
        target: one target; all when omitted.
    """
    console.out(runner.describe(Plane.ENHANCER, target), highlight=False)


async def promote(
    run: str = LATEST,
    *,
    nous: Path,
    ids: tuple[str, ...] = (),
    all_verdicts: bool = False,
    yes: bool = False,
    promoter: Inject[PlanePromote],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Apply RUN's promotable patches to the checkout and record what happened; a human command, asks first.

    Args:
        run: an enhancer run id, or `latest`.
        nous: the e-nous checkout the patches land in.
        ids: `propose` verdicts to apply besides the `adopt` ones.
        all_verdicts: apply every promotable verdict.
        yes: apply without asking.
    """
    human_guard(settings, terminal=sys.stdin.isatty())
    match await human_confirm(f"promote {run} into {nous}?", yes=yes):
        case False:
            msg = "promote aborted: nothing written"
            raise RefusedError(msg)
        case _:
            promotion, record = await promoter.run(nous, run, ids, everything=all_verdicts)
    lines = (
        f"applied  {', '.join(promotion.applied) or '—'}",
        f"already  {', '.join(promotion.already) or '—'}",
        *(f"refused  {subject}: {why}" for subject, why in promotion.refused.items()),
        f"→ {record}",
        "next: git commit · taxis transpile run --target <backend> --nous <checkout> --yes",
    )
    _ = [console.out(line, highlight=False) for line in lines]
    ### a mapping pattern matches any superset: `case {}` would take a refusal for success.
    match tuple(promotion.refused):
        case ():
            pass
        case refused:
            msg = f"{len(refused)} patch(es) refused: {', '.join(refused)}"
            raise RefusedError(msg)
