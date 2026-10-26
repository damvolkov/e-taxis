"""commands.transpile: driving adapter for the transpiler — an e-nous checkout held to its schema and its specs.

`check` reads the checkout at a ref (HEAD by default; `--worktree` as it stands), validates the core against
`core/schema.yaml` and every spec against `specs/base.yaml`, then runs each spec's law. It prints one line per
finding, grouped by backend, and the stamp; a blocking finding makes the run fail. Nothing is written."""

from itertools import groupby
from pathlib import Path

import msgspec
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from e_taxis.harness.commands.stack import HEADER
from e_taxis.harness.runtime.deps import Inject
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.error import CheckError
from e_taxis.transpile.models.report import Report
from e_taxis.transpile.services.check import CheckService


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
