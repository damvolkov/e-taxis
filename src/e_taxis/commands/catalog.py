"""commands.catalog: driving adapter for the catalog itself — `map` shows it, `doctor` checks it."""

import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.models.catalog import Target
from e_taxis.models.error import DoctorError
from e_taxis.runtime.deps import Inject
from e_taxis.services.doctor import DoctorService
from e_taxis.services.resolver import ResolverService

##### DEFAULTS #####
HEADER: str = "bold #6f9bff"
ABSENT: str = "—"


##### COMMANDS #####
async def mapping(
    *, target: Target | None = None, json: bool = False, resolver: Inject[ResolverService], console: Inject[Console]
) -> None:
    """The catalog: every entry, where it applies, how each profile takes it, when it was last checked.

    Args:
        target: only the entries serving this target.
        json: the entries as JSON, for machines.
    """
    entries = await resolver.listing(target)
    profiles = sorted({name for entry in entries for name in entry.status.profile})
    table = Table("id", "kind", "targets", "scope", *profiles, "checked", box=None, header_style=HEADER)
    _ = [
        table.add_row(
            entry.id,
            entry.kind,
            ", ".join(entry.targets),
            entry.scope,
            *(entry.status.profile.get(name, ABSENT) for name in profiles),
            entry.status.checked.isoformat(),
        )
        for entry in entries
    ]
    match json:
        case True:
            console.out(msgspec.json.encode(entries).decode(), highlight=False)
        case _:
            console.print(table if table.row_count else "[dim]the catalog is empty[/]")


async def doctor(*, json: bool = False, doctor: Inject[DoctorService], console: Inject[Console]) -> None:
    """Catalog integrity: schema, unique ids, requires resolve without a cycle, primitives fit targets, one owner per key.

    Args:
        json: the report as JSON, for machines.
    """
    report = await doctor.run()
    table = Table("rule", "id", "detail", box=None, header_style=HEADER)
    _ = [table.add_row(problem.rule, problem.id, problem.detail) for problem in report.problems]
    match (json, report.problems):
        case (True, _):
            console.out(msgspec.json.encode(report).decode(), highlight=False)
        case (False, ()):
            console.print(f"[green]✓[/] {report.checked} entries, no problem")
        case _:
            console.print(table)
    match report.problems:
        case ():
            pass
        case problems:
            msg = f"{len(problems)} problem(s) in {report.checked} entries"
            raise DoctorError(msg)
