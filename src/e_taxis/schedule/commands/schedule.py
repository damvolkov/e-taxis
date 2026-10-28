"""commands.schedule: driving adapter for unattended runs — `taxis schedule list | apply | run --nous PATH`.

The schedules are data in an e-nous checkout (`core/tekton/config/schedules.yaml`), read as the checkout stands, and
live as systemd user timers `taxis-<id>` in TAXIS_SCHEDULE_UNITS. `list` shows each one's state, orphans included;
`apply` prints the plan and writes nothing unless `--yes`; `run` starts one through systemd now and waits for it,
exiting 33 after its state when the result is not `success`. A refusal (shape, calendar, unknown id) exits 32."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

import msgspec
from rich.console import Console
from rich.table import Table

from e_taxis.harness.commands.stack import HEADER
from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.schedule.models.error import ScheduleRunError
from e_taxis.schedule.models.schedule import ScheduleAction, ScheduleState
from e_taxis.schedule.services.schedule import ScheduleService
from e_taxis.transpile.adapters.nous import GitNous

##### DEFAULTS #####
DRY: Final[str] = "[dim]dry run — nothing written; pass --yes to apply it[/]"
STYLES: Final[Mapping[ScheduleAction, str]] = MappingProxyType(
    {
        ScheduleAction.CREATE: "green",
        ScheduleAction.UPDATE: "yellow",
        ScheduleAction.REMOVE: "red",
        ScheduleAction.KEEP: "dim",
    }
)
### (declared, off, installed) → what `list` calls it; an undeclared schedule is never off.
STATES: Final[Mapping[tuple[bool, bool, bool], str]] = MappingProxyType(
    {
        (True, False, True): "installed",
        (True, False, False): "absent",
        (True, True, False): "off",
        (True, True, True): "off·installed",
        (False, False, True): "orphan",
    }
)


##### UTILITIES #####
def render_result(state: ScheduleState) -> str:
    """The service's last result and exit status, `success (0)`; empty when systemd has none."""
    return f"{state.result} ({state.status})" if state.status else state.result


##### COMMANDS #####
async def listing(
    *, nous: Nous = UNSET, json: bool = False, scheduler: Inject[ScheduleService], console: Inject[Console]
) -> None:
    """Every declared schedule and every installed `taxis-*` unit no longer declared, with its state.

    Args:
        nous: the e-nous checkout, read as it stands.
        json: the states as JSON, for machines.
    """
    states = await scheduler.status(GitNous(nous, None))
    table = Table("id", "state", "enabled", "next", "last", "result", box=None, header_style=HEADER)
    _ = [
        table.add_row(
            state.id,
            STATES[state.declared, state.off, state.installed],
            state.enabled,
            state.next,
            state.last,
            render_result(state),
        )
        for state in states
    ]
    match json:
        case True:
            console.out(msgspec.json.encode(states).decode(), highlight=False)
        case _:
            console.print(table if table.row_count else "[dim]no schedule declared or installed[/]")


async def apply(
    *,
    nous: Nous = UNSET,
    yes: bool = False,
    json: bool = False,
    scheduler: Inject[ScheduleService],
    console: Inject[Console],
) -> None:
    """Render the core's schedules into systemd user timers: create, update, remove, keep. Dry unless --yes.

    Args:
        nous: the e-nous checkout, read as it stands.
        yes: write the units and drive systemctl. Without it, apply only prints the plan.
        json: the plan as JSON, for machines.
    """
    source = GitNous(nous, None)
    plan = await (scheduler.apply(source) if yes else scheduler.plan(source))
    table = Table("id", "action", box=None, header_style=HEADER)
    _ = [table.add_row(step.id, f"[{STYLES[step.action]}]{step.action}[/]") for step in plan.steps]
    match json:
        case True:
            console.out(msgspec.json.encode(plan).decode(), highlight=False)
        case _:
            console.print(table if table.row_count else "[dim]no schedule declared or installed[/]")
            console.print("[green]applied[/]" if yes else DRY)


async def run(ident: str, *, nous: Nous = UNSET, scheduler: Inject[ScheduleService], console: Inject[Console]) -> None:
    """Run IDENT now through systemd and wait for it; exits 33 when its result is not success.

    Args:
        ident: a schedule id declared and installed (see `taxis schedule list`).
        nous: the e-nous checkout, read as it stands.
    """
    state = await scheduler.run(GitNous(nous, None), ident)
    console.out(f"{state.id} {render_result(state)}", highlight=False)
    match state.result:
        case "success":
            pass
        case _:
            msg = f"schedule {state.id} ended {render_result(state)}"
            raise ScheduleRunError(msg)
