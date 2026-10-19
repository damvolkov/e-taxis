"""commands.install: driving adapter for the writing half — `apply` carries a target's plan out, `uninstall`
takes one part back out.

Both are dry by default: without `--yes` they print what they would do and exit 0, having written
nothing (`--dry-run` keeps it so even beside `--yes`). With `--yes`, every change goes through the
undo journal — `taxis history undo` reverts the run. A refused apply, a failed step or a failed verify
exits 10; a failed uninstall exits 11 — always after the full report."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.commands.stack import HEADER, STYLES
from e_taxis.models.apply import ApplyOptions, ApplyStatus
from e_taxis.models.catalog import Target
from e_taxis.models.error import ApplyError, UninstallError
from e_taxis.models.uninstall import UninstallStatus
from e_taxis.runtime.deps import Inject
from e_taxis.runtime.settings import TaxisSettings
from e_taxis.runtime.source import FlagSource
from e_taxis.services.apply import ApplyService
from e_taxis.services.uninstall import UninstallService

##### DEFAULTS #####
DRY: str = "[dim]dry run — nothing written; pass --yes to apply it[/]"
APPLIED: Final[Mapping[ApplyStatus, str]] = MappingProxyType(
    {
        ApplyStatus.APPLIED: "green",
        ApplyStatus.SKIPPED: "dim",
        ApplyStatus.DEFERRED: "cyan",
        ApplyStatus.FAILED: "red",
        ApplyStatus.NOT_RUN: "dim",
    }
)
REMOVED: Final[Mapping[UninstallStatus, str]] = MappingProxyType(
    {
        UninstallStatus.REMOVED: "green",
        UninstallStatus.PLANNED: "yellow",
        UninstallStatus.ABSENT: "dim",
        UninstallStatus.DEFERRED: "cyan",
        UninstallStatus.FAILED: "red",
        UninstallStatus.NOT_RUN: "dim",
    }
)


##### COMMANDS #####
async def apply(
    *,
    target: Target,
    profile: str | None = None,
    engineer: Path | None = None,
    only: str = "",
    dry_run: bool = False,
    yes: bool = False,
    accept_licence: tuple[str, ...] = (),
    confirm: tuple[str, ...] = (),
    json: bool = False,
    applier: Inject[ApplyService],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Install what the plan says for one target, in requires order, verified, undoable. Dry unless --yes.

    Args:
        target: the harness to apply for.
        profile: a profile shipped with the catalog.
        engineer: an e-engineer checkout whose stack registry says what is wanted.
        only: comma-separated ids: apply just these steps of the plan.
        dry_run: print the plan and write nothing, even with --yes.
        yes: write. Without it, apply only prints the plan.
        accept_licence: open the licence gate of this entry id (repeatable).
        confirm: open the confirmation gate of this entry id (repeatable).
        json: the plan (dry) or the report as JSON, for machines.
    """
    source = FlagSource(settings.taxis_catalog, profile=profile, engineer=engineer)
    picked = frozenset(part for part in only.split(",") if part)
    match yes and not dry_run:
        case False:
            plan = await applier.plan(source, target, picked)
            table = Table("id", "action", "reason", box=None, header_style=HEADER)
            _ = [table.add_row(step.id, f"[{STYLES[step.action]}]{step.action}[/]", step.reason) for step in plan.steps]
            match json:
                case True:
                    console.out(msgspec.json.encode(plan).decode(), highlight=False)
                case _:
                    console.print(table if table.row_count else "[dim]nothing wanted for this target[/]")
                    console.print(DRY)
        case _:
            options = ApplyOptions(only=picked, licences=frozenset(accept_licence), confirms=frozenset(confirm))
            report = await applier.run(source, target, options)
            table = Table("id", "status", "detail", box=None, header_style=HEADER)
            _ = [
                table.add_row(step.id, f"[{APPLIED[step.status]}]{step.status}[/]", step.detail)
                for step in report.steps
            ]
            _ = [
                table.add_row(
                    result.id, "[green]pass[/]" if result.passed else "[red]fail[/]", f"verify · {result.detail}"
                )
                for result in report.verify
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
                    msg = f"{len(failed)} part(s) failed: {', '.join(failed)} — `taxis history undo` reverts what was written"
                    raise ApplyError(msg)


async def uninstall(
    part: str,
    /,
    *,
    target: Target,
    cascade: bool = False,
    yes: bool = False,
    uninstaller: Inject[UninstallService],
    console: Inject[Console],
) -> None:
    """Take one part out through its uninstall recipe; with --cascade, what requires it first. Dry unless --yes.

    Args:
        part: the entry id to uninstall.
        target: the harness to uninstall from.
        cascade: also uninstall every entry that requires this one, dependents first.
        yes: write. Without it, uninstall only prints what it would remove.
    """
    report = await uninstaller.run(part, target, cascade=cascade, write=yes)
    table = Table("id", "status", "detail", box=None, header_style=HEADER)
    _ = [table.add_row(step.id, f"[{REMOVED[step.status]}]{step.status}[/]", step.detail) for step in report.steps]
    console.print(table)
    match (yes, report.failed):
        case (False, _):
            console.print(DRY.replace("apply", "uninstall"))
        case (True, ()):
            pass
        case _:
            msg = f"{len(report.failed)} part(s) failed to uninstall: {', '.join(report.failed)}"
            raise UninstallError(msg)
