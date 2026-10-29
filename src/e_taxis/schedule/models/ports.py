"""models.ports: what the schedule service asks of the world — systemd's user manager and the folder it reads units from.

Structural contract only: the adapter owns the units dir and the `systemctl --user` calls behind one port, so a test
runs the whole service against a scripted runner and a temp dir."""

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable


##### PORTS #####
@runtime_checkable
class SystemdPort(Protocol):
    """The units taxis owns (a header-marked `taxis-*.service|.timer`), the manager's view of a unit, the calendar
    check, and the `systemctl --user` verbs; a failed verb is a ScheduleError."""

    async def read(self) -> dict[str, bytes]: ...

    async def write(self, files: Mapping[str, bytes]) -> None: ...

    async def delete(self, names: Iterable[str]) -> None: ...

    async def show(self, unit: str, *props: str) -> dict[str, str]: ...

    async def calendar(self, expr: str) -> bool: ...

    async def control(self, *args: str) -> None: ...
