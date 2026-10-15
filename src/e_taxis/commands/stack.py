"""commands.stack: driving adapter for one target's stack — `plan` what apply would do, `verify` what is there.

Both are read-only. The source is a flag: `--profile NAME` (shipped with the catalog) or `--engineer PATH`
(an e-engineer checkout). A plan with unknown or blocked parts, or a verify with a failure, exits non-zero
after printing the full report."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.models.catalog import Target
from e_taxis.models.error import PlanError, VerifyError
from e_taxis.models.plan import PlanAction
from e_taxis.runtime.deps import Inject
from e_taxis.runtime.settings import TaxisSettings
from e_taxis.runtime.source import FlagSource
from e_taxis.services.plan import PlanService
from e_taxis.services.verify import VerifyService

##### DEFAULTS #####
HEADER: str = "bold #6f9bff"
STYLES: Final[Mapping[PlanAction, str]] = MappingProxyType(
    {
        PlanAction.SKIP: "dim",
        PlanAction.INSTALL: "green",
        PlanAction.UPDATE: "yellow",
        PlanAction.UNKNOWN: "red",
        PlanAction.BLOCKED: "red",
    }
)


##### COMMANDS #####
async def plan(
    *,
    target: Target,
    profile: str | None = None,
    engineer: Path | None = None,
    json: bool = False,
    planner: Inject[PlanService],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """What apply would do for one target: wanted ⨝ catalog, in requires order, probed. Writes nothing.

    Args:
        target: the harness to plan for.
        profile: a profile shipped with the catalog.
        engineer: an e-engineer checkout whose stack registry says what is wanted.
        json: the plan as JSON, for machines.
    """
    source = FlagSource(settings.taxis_catalog, profile=profile, engineer=engineer)
    result = await planner.run(source, target)
    table = Table("id", "action", "reason", box=None, header_style=HEADER)
    _ = [table.add_row(step.id, f"[{STYLES[step.action]}]{step.action}[/]", step.reason) for step in result.steps]
    match json:
        case True:
            console.out(msgspec.json.encode(result).decode(), highlight=False)
        case _:
            console.print(table if table.row_count else "[dim]nothing wanted for this target[/]")
    match result.failed:
        case ():
            pass
        case failed:
            msg = f"{len(failed)} part(s) cannot be planned: {', '.join(step.id for step in failed)}"
            raise PlanError(msg)


async def verify(
    *,
    target: Target,
    profile: str | None = None,
    engineer: Path | None = None,
    json: bool = False,
    verifier: Inject[VerifyService],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Run every wanted part's verify for one target and report each; all run, none stops the rest.

    Args:
        target: the harness to verify.
        profile: a profile shipped with the catalog.
        engineer: an e-engineer checkout whose stack registry says what is wanted.
        json: the report as JSON, for machines.
    """
    source = FlagSource(settings.taxis_catalog, profile=profile, engineer=engineer)
    report = await verifier.run(source, target)
    table = Table("id", "result", "detail", box=None, header_style=HEADER)
    _ = [
        table.add_row(result.id, "[green]pass[/]" if result.passed else "[red]fail[/]", result.detail)
        for result in report.results
    ]
    match json:
        case True:
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case _:
            console.print(table if table.row_count else "[dim]nothing wanted for this target[/]")
    match report.failed:
        case ():
            pass
        case failed:
            msg = f"{len(failed)} part(s) failed verify: {', '.join(result.id for result in failed)}"
            raise VerifyError(msg)
