"""commands.reports: `taxis reports show RUN --nous PATH` — an evaluation's or an enhancement's report, rebuilt from
its ledger (the ledger is the truth; `report.md` is a copy). A workflow run's report is its own `report.md` under
`<nous>/.reports/workflows/<id>/<run>/`."""

import msgspec
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.workflow.services.plane import PlaneRun

##### DEFAULTS #####
LATEST: str = "latest"


##### COMMANDS #####
async def show(
    run: str = LATEST, *, nous: Nous = UNSET, json: bool = False, runner: Inject[PlaneRun], console: Inject[Console]
) -> None:
    """Print RUN's report, rebuilt from its ledger.

    Args:
        run: an evaluator or enhancer run id, or `latest` (the newest of either).
        nous: the e-nous checkout whose `.reports/` holds the run.
        json: the report as JSON (manifest, every node run) instead of Markdown.
    """
    report = await runner.load(await runner.folder(nous, run))
    match json:
        case True:
            console.out(msgspec.json.format(msgspec.json.encode(report)).decode(), highlight=False)
        case _:
            console.out(report.markdown, highlight=False)
