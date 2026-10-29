"""services.schedule: the declared schedules held against the installed units — plan, apply, state, run now.

The declaration is the e-nous core as it stands (`config.tekton.schedules`), converted once into `Schedule`s; a shape
it breaks or a calendar systemd refuses is a ScheduleError naming the id, raised before any file is touched. The plan
is `SchedulePlan.diff` of what the active schedules render against what the units dir holds. Apply carries it out in
an order that leaves no live timer pointing at a deleted file: removed timers stopped and disabled, their files
deleted, created and updated files written, the manager reloaded, then created timers enabled and updated ones
restarted. The taxis binary is the one this process was started as, fixed at construction."""

from contextlib import suppress
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

import msgspec

from e_taxis.schedule.models.error import ScheduleError
from e_taxis.schedule.models.schedule import Ident, Schedule, ScheduleAction, ScheduleKind, SchedulePlan, ScheduleState

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.schedule.models.ports import SystemdPort
    from e_taxis.transpile.models.ports import NousPort

##### DEFAULTS #####
SOURCE: Final[str] = "core/tekton/config/schedules.yaml"
FACET: Final[str] = "tekton"
MODULE: Final[str] = "schedules"
TIMER: Final[tuple[str, ...]] = ("NextElapseUSecRealtime", "LastTriggerUSec", "UnitFileState")
SERVICE: Final[tuple[str, ...]] = ("Result", "ExecMainStatus")
### the verb that brings a written timer live, per action; the others start nothing.
START: Final[Mapping[ScheduleAction, tuple[str, ...]]] = MappingProxyType(
    {ScheduleAction.CREATE: ("enable", "--now"), ScheduleAction.UPDATE: ("restart",)}
)
WRITE: Final[frozenset[ScheduleAction]] = frozenset(START)


##### TYPES #####
class ScheduleService:
    """Plan, apply, state and run of the core's schedules over one SystemdPort."""

    __slots__ = ("_binary", "_systemd")

    def __init__(self, systemd: SystemdPort, binary: Path) -> None:
        self._systemd = systemd
        self._binary = binary

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_schedule(ident: str, body: object) -> Schedule:
        """One declaration typed; msgspec's path does not name a map key, so the error does."""
        try:
            return msgspec.convert({ident: body}, dict[Ident, Schedule])[ident]
        except msgspec.ValidationError as exc:
            msg = f"{SOURCE}: schedule {ident!r}: {exc}"
            raise ScheduleError(msg) from exc

    @classmethod
    async def _common_declared(cls, nous: NousPort) -> tuple[Path, dict[str, Schedule]]:
        """The checkout's root and its schedules by id, in declaration order; none when the module is absent or empty."""
        tree = await nous.load()
        match tree.config[FACET].get(MODULE) or {}:
            case dict() as raw:
                return Path(tree.root), {str(key): cls._common_schedule(str(key), body) for key, body in raw.items()}
            case other:
                msg = f"{SOURCE}: a map id → schedule, not {type(other).__name__}"
                raise ScheduleError(msg)

    async def _common_validate(self, declared: Mapping[str, Schedule]) -> None:
        refused = [
            f"schedule {ident}: systemd refuses calendar {schedule.calendar!r}"
            for ident, schedule in declared.items()
            if not await self._systemd.calendar(schedule.calendar)
        ]
        match refused:
            case []:
                pass
            case _:
                raise ScheduleError("; ".join(refused))

    async def _common_plan(self, nous: NousPort) -> tuple[dict[str, bytes], dict[str, bytes], SchedulePlan]:
        """(rendered, installed, the plan between them), every declaration validated first."""
        root, declared = await self._common_declared(nous)
        await self._common_validate(declared)
        want = {
            name: body
            for ident, schedule in declared.items()
            if not schedule.off
            for name, body in schedule.render(ident, root, self._binary).items()
        }
        have = await self._systemd.read()
        return want, have, SchedulePlan.diff(want, have, tuple(declared))

    async def _common_state(self, ident: str, schedule: Schedule | None, *, installed: bool) -> ScheduleState:
        """One schedule's state; the manager is asked only about installed units."""
        timer = await self._systemd.show(ScheduleKind.TIMER.unit(ident), *TIMER) if installed else {}
        service = await self._systemd.show(ScheduleKind.SERVICE.unit(ident), *SERVICE) if installed else {}
        return ScheduleState(
            id=ident,
            declared=schedule is not None,
            off=bool(schedule and schedule.off),
            installed=installed,
            enabled=timer.get("UnitFileState", ""),
            next=timer.get("NextElapseUSecRealtime", ""),
            last=timer.get("LastTriggerUSec", ""),
            result=service.get("Result", ""),
            status=service.get("ExecMainStatus", ""),
        )

    async def _common_installed(self) -> frozenset[str]:
        return frozenset(ScheduleKind.ident(name) for name in await self._systemd.read())

    ############################################################

    ##### PUBLIC #####

    async def plan(self, nous: NousPort) -> SchedulePlan:
        """What apply would do; writes nothing."""
        *_, plan = await self._common_plan(nous)
        return plan

    async def apply(self, nous: NousPort) -> SchedulePlan:
        """Carry the plan out on the units dir and the user manager; the plan it carried out."""
        want, have, plan = await self._common_plan(nous)
        actions = {step.id: step.action for step in plan.steps}
        gone = [name for name in have if actions[ScheduleKind.ident(name)] is ScheduleAction.REMOVE]
        _ = [
            await self._systemd.control("disable", "--now", name) for name in gone if name.endswith(ScheduleKind.TIMER)
        ]
        await self._systemd.delete(gone)
        await self._systemd.write(
            {name: body for name, body in want.items() if actions[ScheduleKind.ident(name)] in WRITE}
        )
        await self._systemd.control("daemon-reload")
        _ = [
            await self._systemd.control(*START[step.action], ScheduleKind.TIMER.unit(step.id))
            for step in plan.steps
            if step.action in START
        ]
        return plan

    async def status(self, nous: NousPort) -> tuple[ScheduleState, ...]:
        """Every declared schedule, then every installed one no longer declared, with the manager's view of it."""
        _, declared = await self._common_declared(nous)
        installed = await self._common_installed()
        ids = (*declared, *sorted(installed - declared.keys()))
        return tuple(
            [await self._common_state(ident, declared.get(ident), installed=ident in installed) for ident in ids]
        )

    async def run(self, nous: NousPort, ident: str) -> ScheduleState:
        """Start one schedule's service now and wait for it (a oneshot); its state after."""
        _, declared = await self._common_declared(nous)
        match (ident in declared, ident in await self._common_installed()):
            case (False, _):
                msg = f"schedule {ident} is not declared in {SOURCE}"
                raise ScheduleError(msg)
            case (_, False):
                msg = f"schedule {ident} is not installed: run `taxis schedule apply --yes` first"
                raise ScheduleError(msg)
            case _:
                pass
        ### a oneshot that fails makes `start` fail: its Result, read next, says how.
        with suppress(ScheduleError):
            await self._systemd.control("start", ScheduleKind.SERVICE.unit(ident))
        return await self._common_state(ident, declared[ident], installed=True)
