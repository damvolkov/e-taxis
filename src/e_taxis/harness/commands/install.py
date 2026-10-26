"""commands.install: driving adapter for the writing half — `install` mounts a harness whole (the core's brain,
landed by the transpiler from its spec, then the systems around it), `apply` carries a target's plan out,
`uninstall` takes one part back out.

All are dry by default: without `--yes` they print what they would do and exit 0, having written
nothing (`--dry-run` keeps it so even beside `--yes`). With `--yes`, every change goes through the
undo journal — `taxis history undo` reverts the run, an install's two halves together. A target no spec
projects (`system`) has no brain half. A brain that cannot land exits with its transpile code before any
system is touched; a refused apply, a failed step or a failed verify exits 10; a failed uninstall exits 11 —
always after the full report."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import anyio
import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.harness.commands.stack import HEADER, STYLES
from e_taxis.harness.models.apply import ApplyOptions, ApplyStatus
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import ApplyError, UninstallError
from e_taxis.harness.models.uninstall import UninstallStatus
from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.harness.runtime.source import FlagSource
from e_taxis.harness.services.apply import ApplyService
from e_taxis.harness.services.uninstall import UninstallService
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.commands.transpile import render_report
from e_taxis.transpile.services.land import LandService

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
    nous: Path | None = None,
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
        nous: an e-nous checkout whose stack registry says what is wanted.
        only: comma-separated ids: apply just these steps of the plan.
        dry_run: print the plan and write nothing, even with --yes.
        yes: write. Without it, apply only prints the plan.
        accept_licence: open the licence gate of this entry id (repeatable).
        confirm: open the confirmation gate of this entry id (repeatable).
        json: the plan (dry) or the report as JSON, for machines.
    """
    source = FlagSource(settings.taxis_catalog, profile=profile, nous=nous)
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


async def install(
    *,
    target: Target,
    nous: Path,
    profile: str | None = None,
    ref: str = "HEAD",
    worktree: bool = False,
    yes: bool = False,
    accept_licence: tuple[str, ...] = (),
    confirm: tuple[str, ...] = (),
    json: bool = False,
    lander: Inject[LandService],
    applier: Inject[ApplyService],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Mount a harness in order: the core's brain, then the systems and plugins it expects. Dry unless --yes.

    Args:
        target: the harness to mount.
        nous: the e-nous checkout: its core is the brain, its stack registry the systems.
        profile: take the systems from this profile instead of the checkout's stack registry.
        ref: the git ref the core is read at.
        worktree: read the core from the working tree instead of a ref.
        yes: write. Without it, install only prints both plans.
        accept_licence: open the licence gate of this entry id (repeatable).
        confirm: open the confirmation gate of this entry id (repeatable).
        json: each half's plan or report as one JSON line.
    """
    source = GitNous(nous, None if worktree else ref)
    where = Path(await anyio.Path(Path.home()).resolve())
    projected = any(key.rpartition("/")[2] == target for key in (await source.load()).specs)
    match (projected, json):
        case (False, _):
            console.print(f"[dim]no spec projects {target}: no brain to land[/]")
        case (True, True):
            report = await (lander.apply(source, target, where) if yes else lander.plan(source, target, where))
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case _:
            render_report(
                await (lander.apply(source, target, where) if yes else lander.plan(source, target, where)), console
            )
    await apply(
        target=target,
        profile=profile,
        nous=None if profile else nous,
        yes=yes,
        accept_licence=accept_licence,
        confirm=confirm,
        json=json,
        applier=applier,
        settings=settings,
        console=console,
    )
