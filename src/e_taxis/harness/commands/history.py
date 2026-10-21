"""commands.history: driving adapter for the undo journal — every run that wrote to the store, and the way back from the last one."""

from rich.console import Console
from rich.table import Table

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.journal import StoreJournal

##### DEFAULTS #####
HEADER: str = "bold #6f9bff"


async def listing(*, journal: Inject[StoreJournal], console: Inject[Console]) -> None:
    """Every recorded run, newest first."""
    table = Table("when", "command", "changes", box=None, header_style=HEADER)
    for entry in await journal.entries():
        table.add_row(
            entry.at.strftime("%Y-%m-%d %H:%M:%S"), entry.command, str(len(entry.writes) + len(entry.effects))
        )
    console.print(table if table.row_count else "[dim]nothing recorded yet[/]")


async def undo(*, journal: Inject[StoreJournal], console: Inject[Console]) -> None:
    """Revert the last recorded run: every change it made to the world, every key it wrote to the store."""
    entry = await journal.undo()
    console.print(f"[green]✓[/] undid `{entry.command}` · {len(entry.writes) + len(entry.effects)} change(s) reverted")
