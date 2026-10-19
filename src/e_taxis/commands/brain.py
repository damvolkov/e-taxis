"""commands.brain: driving adapter for the first half of a mount — an e-engineer core installed into a harness's tree.

Dry by default: without `--yes` it prints what would move and exits 0, having written nothing. The core is the
checkout's committed HEAD (`--ref` names another, `--worktree` takes the tree as it stands). With `--yes`, every
file, key and registration goes through the undo journal — `taxis history undo` puts the tree back."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.adapters.core import GitCore
from e_taxis.commands.stack import HEADER
from e_taxis.models.brain import BrainAction
from e_taxis.models.catalog import Target
from e_taxis.runtime.deps import Inject
from e_taxis.services.brain import BrainService

##### DEFAULTS #####
DRY: str = "[dim]dry run — nothing written; pass --yes to install it[/]"
COLOURS: Final[Mapping[BrainAction, str]] = MappingProxyType(
    {
        BrainAction.FAITHFUL: "dim",
        BrainAction.ADD: "green",
        BrainAction.UPDATE: "cyan",
        BrainAction.OVERWRITE: "yellow",
        BrainAction.ORPHAN: "dim",
    }
)


##### COMMANDS #####
async def brain(
    *,
    target: Target,
    engineer: Path,
    ref: str = "HEAD",
    worktree: bool = False,
    yes: bool = False,
    json: bool = False,
    projector: Inject[BrainService],
    console: Inject[Console],
) -> None:
    """Install an e-engineer core into a harness's tree, undoable. Dry unless --yes.

    Args:
        target: the harness to install the core into.
        engineer: the e-engineer checkout that holds the core.
        ref: the git ref the core is read at.
        worktree: read the checkout's working tree instead of a ref, uncommitted changes included.
        yes: write. Without it, brain only prints what would move.
        json: the plan as JSON, for machines.
    """
    core = GitCore(engineer, None if worktree else ref)
    plan = await (projector.run(core, target) if yes else projector.plan(core, target))
    table = Table("path", "action", box=None, header_style=HEADER)
    _ = [
        table.add_row(move.path, f"[{COLOURS[move.action]}]{move.action}[/]")
        for move in plan.moves
        if move.action is not BrainAction.FAITHFUL
    ]
    counts = " · ".join(f"{plan.count(action)} {action}" for action in BrainAction if plan.count(action))
    lines = (
        table if table.row_count else f"[dim]{plan.tree} already holds the core[/]",
        f"{plan.target} → {plan.tree} · {counts or 'nothing rendered'}",
        *(() if yes else (DRY,)),
    )
    match json:
        case True:
            console.out(msgspec.json.encode(plan).decode(), highlight=False)
        case _:
            _ = [console.print(line) for line in lines]
