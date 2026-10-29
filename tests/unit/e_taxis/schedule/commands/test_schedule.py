"""tests/unit/e_taxis/schedule/commands/schedule: `taxis schedule list | apply | run` through the real app, over the
scripted runner and the test's own units dir."""

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SHOW_TIMER = ("systemctl", "--user", "show", "taxis-eval-corpus.timer")
SHOW_SERVICE = ("systemctl", "--user", "show", "taxis-eval-corpus.service")


def test_schedule_apply_dry_writes_nothing(
    taxis: Callable[..., tuple[int, str, str]], schedule_nous: Path, units: Path, scripted, binary: Path
) -> None:
    code, out, _ = taxis("schedule", "apply", "--nous", str(schedule_nous))
    assert code == 0
    assert "eval-corpus" in out
    assert "create" in out
    assert "dry run" in out
    assert not units.exists()


def test_schedule_apply_yes_installs_then_keeps(
    taxis: Callable[..., tuple[int, str, str]], schedule_nous: Path, units: Path, scripted, binary: Path
) -> None:
    code, out, _ = taxis("schedule", "apply", "--nous", str(schedule_nous), "--yes")
    _, again, _ = taxis("schedule", "apply", "--nous", str(schedule_nous), "--json")
    assert code == 0
    assert "applied" in out
    assert (
        f"ExecStart={binary} eval run corpus --cadence nightly\n" in (units / "taxis-eval-corpus.service").read_text()
    )
    assert json.loads(again) == {"steps": [{"id": "eval-corpus", "action": "keep"}]}


def test_schedule_apply_refuses_a_calendar(
    taxis: Callable[..., tuple[int, str, str]], schedule_nous: Path, units: Path, scripted, binary: Path
) -> None:
    scripted.failing.add(("systemd-analyze", "calendar"))
    code, _, err = taxis("schedule", "apply", "--nous", str(schedule_nous), "--yes")
    assert code == 32
    assert "schedule eval-corpus: systemd refuses calendar" in err
    assert not units.exists()


@pytest.mark.parametrize(
    ("args", "row"),
    [
        ((), "eval-corpus installed enabled Thu 03:00 Wed 03:00 exit-code (1)"),
        (
            ("--json",),
            (
                '{"id":"eval-corpus","declared":true,"off":false,"installed":true,"enabled":"enabled",'
                '"next":"Thu 03:00","last":"Wed 03:00","result":"exit-code","status":"1"}'
            ),
        ),
    ],
    ids=["table", "json"],
)
def test_schedule_list_shows_the_manager(
    taxis: Callable[..., tuple[int, str, str]],
    schedule_nous: Path,
    units: Path,
    scripted,
    binary: Path,
    args: tuple[str, ...],
    row: str,
) -> None:
    scripted.replies[SHOW_TIMER] = (
        "NextElapseUSecRealtime=Thu 03:00\nLastTriggerUSec=Wed 03:00\nUnitFileState=enabled\n"
    )
    scripted.replies[SHOW_SERVICE] = "Result=exit-code\nExecMainStatus=1\n"
    taxis("schedule", "apply", "--nous", str(schedule_nous), "--yes")
    code, out, _ = taxis("schedule", "list", "--nous", str(schedule_nous), *args)
    assert code == 0
    assert row in [" ".join(line.split()) for line in out.splitlines()] + [out.strip().strip("[]")]


@pytest.mark.parametrize(
    ("ident", "reply", "code", "said"),
    [
        ("eval-corpus", "Result=success\nExecMainStatus=0\n", 0, "eval-corpus success (0)"),
        ("eval-corpus", "Result=exit-code\nExecMainStatus=2\n", 33, "schedule eval-corpus ended exit-code (2)"),
        ("nope", "", 32, "schedule nope is not declared"),
    ],
    ids=["success", "failure", "undeclared"],
)
def test_schedule_run(
    taxis: Callable[..., tuple[int, str, str]],
    schedule_nous: Path,
    units: Path,
    scripted,
    binary: Path,
    ident: str,
    reply: str,
    code: int,
    said: str,
) -> None:
    taxis("schedule", "apply", "--nous", str(schedule_nous), "--yes")
    scripted.replies[SHOW_SERVICE] = reply
    exit_code, out, err = taxis("schedule", "run", ident, "--nous", str(schedule_nous))
    assert exit_code == code
    assert said in out + err
