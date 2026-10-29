"""tests/unit/e_taxis/schedule/services/schedule: the plan over a real e-nous copy, apply's files, validation before any
write, the state of every schedule, and a run through the manager."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.schedule.models.error import ScheduleError
from e_taxis.schedule.models.schedule import HEADER, ScheduleAction, ScheduleState

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.schedule.services.schedule import ScheduleService
    from e_taxis.transpile.adapters.nous import GitNous

ONE = 'a:\n  doc: first\n  calendar: "*-*-* 03:00:00"\n  steps:\n    - [eval, run, corpus]\n'
SHOW_TIMER = ("systemctl", "--user", "show", "taxis-a.timer")
SHOW_SERVICE = ("systemctl", "--user", "show", "taxis-a.service")


async def test_schedule_plan_creates_what_is_declared(
    service: ScheduleService, declare: Callable[[str | None], GitNous]
) -> None:
    plan = await service.plan(declare(ONE))
    assert [(step.id, step.action) for step in plan.steps] == [("a", ScheduleAction.CREATE)]


@pytest.mark.parametrize("text", [None, "{}\n"], ids=["absent", "empty"])
async def test_schedule_plan_without_schedules(
    service: ScheduleService, declare: Callable[[str | None], GitNous], text: str | None
) -> None:
    assert (await service.plan(declare(text))).steps == ()


async def test_schedule_apply_writes_the_pair(
    service: ScheduleService, declare: Callable[[str | None], GitNous], units: Path, schedule_nous: Path
) -> None:
    nous = declare(ONE)
    await service.apply(nous)
    service_unit = (units / "taxis-a.service").read_text()
    assert sorted(path.name for path in units.iterdir()) == ["taxis-a.service", "taxis-a.timer"]
    assert service_unit.startswith(f"{HEADER}\n")
    assert f"WorkingDirectory={schedule_nous}\n" in service_unit
    assert "ExecStart=/opt/taxis/bin/taxis eval run corpus\n" in service_unit
    assert [step.action for step in (await service.plan(nous)).steps] == [ScheduleAction.KEEP]


@pytest.mark.parametrize(
    ("change", "action", "files"),
    [
        (
            ONE.replace("03:00", "04:00"),
            ScheduleAction.UPDATE,
            {
                "taxis-a.service": "ExecStart=/opt/taxis/bin/taxis eval run corpus",
                "taxis-a.timer": "OnCalendar=*-*-* 04:00:00",
            },
        ),
        (ONE + "  off: true\n", ScheduleAction.REMOVE, {}),
        ("{}\n", ScheduleAction.REMOVE, {}),
    ],
    ids=["update", "off", "undeclared"],
)
async def test_schedule_apply_follows_the_core(
    service: ScheduleService,
    declare: Callable[[str | None], GitNous],
    units: Path,
    change: str,
    action: ScheduleAction,
    files: dict[str, str],
) -> None:
    await service.apply(declare(ONE))
    plan = await service.apply(declare(change))
    assert [(step.id, step.action) for step in plan.steps] == [("a", action)]
    assert {path.name for path in units.iterdir()} == files.keys()
    assert all(f"{line}\n" in (units / name).read_text() for name, line in files.items())


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("- [eval]\n", "a map id → schedule, not list"),
        ('a:\n  doc: d\n  calendar: "bogus"\n  steps: [[eval]]\n', "schedule a: systemd refuses calendar 'bogus'"),
        ("a:\n  doc: d\n  calendar: daily\n  steps: []\n", "steps"),
        ("a:\n  doc: d\n  calendar: daily\n  steps: [[]]\n", "steps"),
        ("a:\n  doc: d\n  calendar: daily\n  steps: [[eval]]\n  when: now\n", "when"),
        ("a b:\n  doc: d\n  calendar: daily\n  steps: [[eval]]\n", "schedule 'a b'"),
    ],
    ids=["not-a-map", "calendar", "no-steps", "empty-argv", "unknown-field", "bad-id"],
)
async def test_schedule_apply_refuses_before_writing(
    service: ScheduleService, declare: Callable[[str | None], GitNous], units: Path, scripted, text: str, names: str
) -> None:
    scripted.failing.add(("systemd-analyze", "calendar", "bogus"))
    with pytest.raises(ScheduleError, match=names):
        await service.apply(declare(text))
    assert not units.exists()


async def test_schedule_status_reads_the_manager(
    service: ScheduleService, declare: Callable[[str | None], GitNous], systemd, scripted
) -> None:
    scripted.replies[SHOW_TIMER] = (
        "NextElapseUSecRealtime=Thu 03:00\nLastTriggerUSec=Wed 03:00\nUnitFileState=enabled\n"
    )
    scripted.replies[SHOW_SERVICE] = "Result=exit-code\nExecMainStatus=1\n"
    nous = declare(ONE + "b:\n  doc: second\n  calendar: daily\n  steps: [[eval]]\n  off: true\n")
    await service.apply(nous)
    await systemd.write({"taxis-old.timer": f"{HEADER}\n".encode()})
    assert await service.status(nous) == (
        ScheduleState(
            id="a",
            declared=True,
            installed=True,
            enabled="enabled",
            next="Thu 03:00",
            last="Wed 03:00",
            result="exit-code",
            status="1",
        ),
        ScheduleState(id="b", declared=True, off=True, installed=False),
        ScheduleState(id="old", declared=False, installed=True),
    )


@pytest.mark.parametrize(
    ("text", "names"),
    [(ONE, "schedule a is not installed"), ("{}\n", "schedule a is not declared")],
    ids=["absent", "undeclared"],
)
async def test_schedule_run_refuses(
    service: ScheduleService, declare: Callable[[str | None], GitNous], text: str, names: str
) -> None:
    with pytest.raises(ScheduleError, match=names):
        await service.run(declare(text), "a")


@pytest.mark.parametrize(
    ("failing", "reply", "result"),
    [
        (False, "Result=success\nExecMainStatus=0\n", "success"),
        (True, "Result=exit-code\nExecMainStatus=2\n", "exit-code"),
    ],
    ids=["success", "failure"],
)
async def test_schedule_run_reports_the_result(
    service: ScheduleService,
    declare: Callable[[str | None], GitNous],
    scripted,
    failing: bool,
    reply: str,
    result: str,
) -> None:
    nous = declare(ONE)
    await service.apply(nous)
    scripted.replies[SHOW_SERVICE] = reply
    scripted.failing |= {("systemctl", "--user", "start")} if failing else set()
    assert (await service.run(nous, "a")).result == result


async def test_schedule_apply_surfaces_a_failed_verb(
    service: ScheduleService, declare: Callable[[str | None], GitNous], scripted
) -> None:
    scripted.failing.add(("systemctl", "--user", "enable"))
    with pytest.raises(ScheduleError, match=r"enable --now taxis-a\.timer"):
        await service.apply(declare(ONE))
