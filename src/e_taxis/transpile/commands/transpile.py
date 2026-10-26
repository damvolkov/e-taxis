"""commands.transpile: driving adapter for the transpiler — an e-nous checkout held to its schema and its specs.

`check` reads the checkout at a ref (HEAD by default; `--worktree` as it stands), validates the core against
`core/schema.yaml` and every spec against `specs/base.yaml`, then runs each spec's law. It prints one line per
finding, grouped by backend, and the stamp; a blocking finding makes the run fail. Nothing is written."""

from collections import Counter
from itertools import groupby
from pathlib import Path

import anyio
import msgspec
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from e_taxis.harness.commands.stack import HEADER
from e_taxis.harness.runtime.deps import Inject
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.error import CheckError, TrialError
from e_taxis.transpile.models.ports import CapturePort
from e_taxis.transpile.models.report import Report
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import LandService
from e_taxis.transpile.services.reverse import ReverseService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService


##### UTILITIES #####
def render_report(report: Report, console: Console) -> None:
    """Findings grouped by backend, each with the spec row and the core paths behind it; then the stamp and the counts."""
    ordered = sorted(report.findings, key=lambda finding: (finding.backend, finding.path, finding.where))
    tables = [
        (backend, Table("kind", "path", "row", "core", "detail", box=None, header_style=HEADER))
        for backend, _ in groupby(ordered, key=lambda finding: finding.backend)
    ]
    _ = [
        table.add_row(
            finding.kind,
            escape(finding.path),
            finding.where,
            escape(", ".join(finding.sources)),
            escape(finding.detail),
        )
        for backend, table in tables
        for finding in ordered
        if finding.backend == backend
    ]
    _ = [console.print(f"[bold]{backend}[/]", table) for backend, table in tables]
    specs = " · ".join(f"{name} {version}" for name, version in sorted(report.stamp.specs.items()))
    counts = Counter(finding.kind.value for finding in report.findings)
    console.print(f"{report.stamp.root} @ {report.stamp.commit} · model {report.stamp.model} · {specs}")
    console.print(" · ".join(f"{count} {kind}" for kind, count in sorted(counts.items())) or "nothing to report")


##### COMMANDS #####
async def check(
    *,
    nous: Path,
    ref: str = "HEAD",
    worktree: bool = False,
    json: bool = False,
    checker: Inject[CheckService],
    console: Inject[Console],
) -> None:
    """Hold an e-nous checkout to its schema and to every spec's law. Writes nothing.

    Args:
        nous: the e-nous checkout.
        ref: the git ref core and specs are read at, together.
        worktree: read the checkout as it stands, uncommitted changes included.
        json: the report as JSON, for machines.
    """
    report = await checker.run(GitNous(nous, None if worktree else ref))
    match json:
        case True:
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case _:
            render_report(report, console)
    match report.blocking:
        case ():
            pass
        case blocking:
            msg = f"{len(blocking)} blocking finding(s) in {nous}"
            raise CheckError(msg)


async def run(
    *,
    target: str,
    nous: Path,
    out: Path | None = None,
    home: Path | None = None,
    ref: str = "HEAD",
    worktree: bool = False,
    yes: bool = False,
    json: bool = False,
    runner: Inject[RunService],
    lander: Inject[LandService],
    console: Inject[Console],
) -> None:
    """Project an e-nous core for one backend: plan it against the live tree, land it with --yes, or export it.

    Args:
        target: the backend, by its spec's name (claudecode, opencode, hermes, openhuman).
        nous: the e-nous checkout.
        out: export into this directory instead — a pure render, never a live tree.
        home: the HOME whose tree is planned or landed (default: yours).
        ref: the git ref core and specs are read at, together.
        worktree: read the checkout as it stands, uncommitted changes included.
        yes: land the plan, through the undo journal. Without it, nothing is written.
        json: the projection summary or the plan's report as JSON.
    """
    source = GitNous(nous, None if worktree else ref)
    match (out, yes):
        case (Path() as directory, _):
            projection = await runner.run(source, target, Path(await anyio.Path(directory).resolve()))
            summary = {
                "backend": projection.backend,
                "out": projection.out,
                "files": sorted(projection.files),
                "registry": {name: sorted(entries) for name, entries in projection.registry.items()},
            }
            entries = sum(len(entries) for entries in projection.registry.values())
            lines = (
                f"{projection.backend} → {projection.out} · {len(projection.files)} files · {entries} registry entries",
            )
            match json:
                case True:
                    console.out(msgspec.json.encode(summary).decode(), highlight=False)
                case _:
                    _ = [console.print(line) for line in lines]
        case _:
            where = Path(await anyio.Path(home or Path.home()).resolve())
            report = await (lander.apply(source, target, where) if yes else lander.plan(source, target, where))
            match json:
                case True:
                    console.out(msgspec.json.encode(report).decode(), highlight=False)
                case _:
                    render_report(report, console)
                    console.print(
                        "[dim]plan only — nothing written; pass --yes to land it[/]"
                        if not yes
                        else f"landed {target} under {where} · `taxis history undo` reverts it"
                    )


async def trial(
    *,
    target: str,
    nous: Path,
    ref: str = "HEAD",
    worktree: bool = False,
    json: bool = False,
    prover: Inject[TrialService],
    capture: Inject[CapturePort],
    console: Inject[Console],
) -> None:
    """Raise the real harness on a sandboxed home, fenced, and check it loaded what the core renders.

    Args:
        target: the backend, by its spec's name.
        nous: the e-nous checkout.
        ref: the git ref core and specs are read at, together.
        worktree: read the checkout as it stands, uncommitted changes included.
        json: the trial report as JSON.
    """
    report = await prover.run(GitNous(nous, None if worktree else ref), target, capture)
    match json:
        case True:
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case _:
            table = Table("entity", "probes", "seen", "missing", box=None, header_style=HEADER)
            _ = [
                table.add_row(
                    sight.entity,
                    ", ".join(sight.probes),
                    f"{sight.expected - len(sight.missing)}/{sight.expected}",
                    escape(", ".join(sight.missing)[:200]),
                )
                for sight in report.sights
            ]
            console.print(table)
            console.print(
                f"{report.backend}: {len(report.runs)} probe(s) · {report.captured} reached the model · {'held' if report.held else 'NOT held'}"
            )
    match report.held:
        case True:
            pass
        case _:
            msg = f"{report.backend}: the phantom did not show everything the core renders"
            raise TrialError(msg)


async def reverse(
    *,
    target: str,
    nous: Path,
    home: Path | None = None,
    ref: str = "HEAD",
    worktree: bool = False,
    json: bool = False,
    reader: Inject[ReverseService],
    console: Inject[Console],
) -> None:
    """Read the live tree back toward the core: who moved each fragment since the last landing. Writes nothing.

    Args:
        target: the backend, by its spec's name.
        nous: the e-nous checkout.
        home: the HOME whose tree is read (default: yours).
        ref: the git ref core and specs are read at, together.
        worktree: read the checkout as it stands, uncommitted changes included.
        json: the report as JSON.
    """
    where = Path(await anyio.Path(home or Path.home()).resolve())
    report = await reader.run(GitNous(nous, None if worktree else ref), target, where)
    match json:
        case True:
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case _:
            render_report(report, console)
