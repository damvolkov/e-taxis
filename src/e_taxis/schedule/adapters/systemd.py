"""adapters.systemd: the user manager through `systemctl --user` and `systemd-analyze`, and the units dir it reads.

Every process goes through the RunnerPort (argv, no shell, stdin closed). Ownership is by name and by header: only a
`taxis-*.service|.timer` whose first line is `HEADER` is read as taxis's, so a hand-written unit in the same dir is
never listed, rewritten or deleted. The dir is created on the first write."""

from typing import TYPE_CHECKING

import anyio

from e_taxis.harness.models.error import RunnerError
from e_taxis.schedule.models.error import ScheduleError
from e_taxis.schedule.models.schedule import HEADER, PREFIX, ScheduleKind

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from e_taxis.harness.models.ports import RunnerPort

##### DEFAULTS #####
SUFFIXES: frozenset[str] = frozenset(ScheduleKind)
MARK: bytes = HEADER.encode()


##### TYPES #####
class UserSystemd:
    """Satisfies SystemdPort over one units dir."""

    __slots__ = ("_runner", "_units")

    def __init__(self, runner: RunnerPort, units: Path) -> None:
        self._runner = runner
        self._units = anyio.Path(units)

    ##### PRIVATE METHODS #####

    async def _common_run(self, *argv: str) -> str:
        try:
            return await self._runner.run(argv)
        except RunnerError as exc:
            raise ScheduleError(exc.message) from exc

    ############################################################

    ##### PUBLIC #####

    async def read(self) -> dict[str, bytes]:
        """Every unit file taxis owns, by name; nothing when the dir does not exist."""
        match await self._units.is_dir():
            case False:
                return {}
            case _:
                found = {
                    path.name: await path.read_bytes()
                    async for path in self._units.glob(f"{PREFIX}*")
                    if path.suffix in SUFFIXES
                }
                return {name: body for name, body in found.items() if body.split(b"\n", 1)[0] == MARK}

    async def write(self, files: Mapping[str, bytes]) -> None:
        await self._units.mkdir(parents=True, exist_ok=True)
        _ = [await self._units.joinpath(name).write_bytes(body) for name, body in files.items()]

    async def delete(self, names: Iterable[str]) -> None:
        _ = [await self._units.joinpath(name).unlink(missing_ok=True) for name in names]

    async def show(self, unit: str, *props: str) -> dict[str, str]:
        """The manager's properties of one unit, verbatim; an unknown unit answers them empty, never fails."""
        output = await self._common_run("systemctl", "--user", "show", unit, "-p", ",".join(props))
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    async def calendar(self, expr: str) -> bool:
        """Whether systemd parses `expr` as an OnCalendar value — its own check, not a copy of its grammar."""
        try:
            await self._runner.run(("systemd-analyze", "calendar", expr))
        except RunnerError:
            return False
        return True

    async def control(self, *args: str) -> None:
        await self._common_run("systemctl", "--user", *args)
