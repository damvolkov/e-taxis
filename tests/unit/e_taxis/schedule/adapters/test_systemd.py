"""tests/unit/e_taxis/schedule/adapters/systemd: ownership by name and header, the units dir round trip, `show` parsed,
the calendar check and a failed verb, all over the scripted runner."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.schedule.models.error import ScheduleError
from e_taxis.schedule.models.schedule import HEADER

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.schedule.adapters.systemd import UserSystemd

OURS = f"{HEADER}\n[Timer]\n".encode()


async def test_systemd_read_without_a_units_dir(systemd: UserSystemd) -> None:
    assert await systemd.read() == {}


async def test_systemd_read_keeps_only_what_taxis_owns(systemd: UserSystemd, units: Path) -> None:
    units.mkdir()
    files = {
        "taxis-a.service": OURS,
        "taxis-a.timer": OURS,
        "taxis-b.service": b"[Service]\n",
        "taxis-c.conf": OURS,
        "other.timer": OURS,
        "taxis-empty.timer": b"",
    }
    _ = [(units / name).write_bytes(body) for name, body in files.items()]
    assert await systemd.read() == {"taxis-a.service": OURS, "taxis-a.timer": OURS}


async def test_systemd_write_then_delete(systemd: UserSystemd, units: Path) -> None:
    await systemd.write({"taxis-a.service": OURS, "taxis-a.timer": OURS})
    (units / "other.timer").write_bytes(OURS)
    await systemd.delete(["taxis-a.timer", "taxis-gone.timer"])
    assert sorted(path.name for path in units.iterdir()) == ["other.timer", "taxis-a.service"]


async def test_systemd_show_parses_properties(systemd: UserSystemd, scripted) -> None:
    scripted.replies[("systemctl", "--user", "show", "taxis-a.timer")] = (
        "NextElapseUSecRealtime=Thu 2026-10-29 03:00:00 CET\nLastTriggerUSec=\nUnitFileState=enabled\n"
    )
    assert await systemd.show("taxis-a.timer", "NextElapseUSecRealtime", "LastTriggerUSec", "UnitFileState") == {
        "NextElapseUSecRealtime": "Thu 2026-10-29 03:00:00 CET",
        "LastTriggerUSec": "",
        "UnitFileState": "enabled",
    }


@pytest.mark.parametrize(("failing", "valid"), [(False, True), (True, False)], ids=["valid", "invalid"])
async def test_systemd_calendar(systemd: UserSystemd, scripted, failing: bool, valid: bool) -> None:
    scripted.failing |= {("systemd-analyze", "calendar", "bogus")} if failing else set()
    assert await systemd.calendar("bogus") is valid


async def test_systemd_control_failure_is_typed(systemd: UserSystemd, scripted) -> None:
    scripted.failing.add(("systemctl", "--user", "restart"))
    with pytest.raises(ScheduleError, match=r"systemctl --user restart taxis-a\.timer` exited 1"):
        await systemd.control("restart", "taxis-a.timer")
