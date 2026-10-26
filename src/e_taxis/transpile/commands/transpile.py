"""commands.transpile: driving adapter for the transpiler — an e-nous checkout held to its schema and its specs.

`check` reads the checkout at a ref (HEAD by default; `--worktree` as it stands), validates the core against
`core/schema.yaml` and every spec against `specs/base.yaml`, then runs each spec's law. It prints one line per
finding, grouped by backend, and the stamp; a blocking finding makes the run fail. Nothing is written."""

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
from e_taxis.transpile.models.error import CheckError, TranspileError, TrialError
from e_taxis.transpile.models.ports import CapturePort
from e_taxis.transpile.models.report import Report
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService


##### UTILITIES #####
def render_report(report: Report, console: Console) -> None:
    """Findings by backend, then the stamp and the count; clean when nothing blocks."""
    ordered = sorted(report.findings, key=lambda finding: (finding.backend, finding.where))
    tables = [
        (backend, Table("kind", "where", "path", "detail", box=None, header_style=HEADER))
        for backend, _ in groupby(ordered, key=lambda finding: finding.backend)
    ]
    _ = [
        table.add_row(finding.kind, finding.where, escape(finding.path), escape(finding.detail))
        for backend, table in tables
        for finding in ordered
        if finding.backend == backend
    ]
    _ = [console.print(f"[bold]{backend}[/]", table) for backend, table in tables]
    specs = " · ".join(f"{name} {version}" for name, version in sorted(report.stamp.specs.items()))
    console.print(f"{report.stamp.root} @ {report.stamp.commit} · model {report.stamp.model} · {specs}")
    console.print(f"{len(report.blocking)} blocking · {len(report.findings) - len(report.blocking)} signal")


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
    ref: str = "HEAD",
    worktree: bool = False,
    json: bool = False,
    runner: Inject[RunService],
    console: Inject[Console],
) -> None:
    """Project an e-nous core for one backend. With --out, a pure export into that directory.

    Args:
        target: the backend, by its spec's name (claudecode, opencode, hermes, openhuman).
        nous: the e-nous checkout.
        out: an empty or scratch directory the render is written into; never a live tree.
        ref: the git ref core and specs are read at, together.
        worktree: read the checkout as it stands, uncommitted changes included.
        json: the projection's files and registry entries as JSON.
    """
    match out:
        case None:
            msg = "transpile run lands in a live tree in a later phase: pass --out DIR for a pure export"
            raise TranspileError(msg)
        case _:
            projection = await runner.run(
                GitNous(nous, None if worktree else ref), target, Path(await anyio.Path(out).resolve())
            )
    summary = {
        "backend": projection.backend,
        "out": projection.out,
        "files": sorted(projection.files),
        "registry": {name: sorted(entries) for name, entries in projection.registry.items()},
    }
    match json:
        case True:
            console.out(msgspec.json.encode(summary).decode(), highlight=False)
        case _:
            entries = sum(len(entries) for entries in projection.registry.values())
            console.print(
                f"{projection.backend} → {projection.out} · {len(projection.files)} files · {entries} registry entries"
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
