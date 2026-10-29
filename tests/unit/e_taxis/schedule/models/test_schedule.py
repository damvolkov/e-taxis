"""tests/unit/e_taxis/schedule/models/schedule: the rendered pair byte for byte, systemd's quoting, the plan as a pure diff."""

from pathlib import Path

import pytest

from e_taxis.schedule.models.schedule import HEADER, Schedule, ScheduleAction, ScheduleKind, SchedulePlan, ScheduleStep

ROOT = Path("/srv/e-nous")
BINARY = Path("/opt/taxis/bin/taxis")
SPEC = Schedule(
    doc="nightly upstream spec drift, then the speckeeper on its needs",
    calendar="*-*-* 03:30:00",
    steps=(
        ("eval", "run", "spec", "--cadence", "nightly"),
        ("enhance", "run", "spec", "--from", "latest", "--cadence", "nightly"),
    ),
)
SERVICE = "taxis-a.service"
TIMER = "taxis-a.timer"


async def test_schedule_render_matches_the_golden(golden: dict[str, bytes]) -> None:
    assert SPEC.render("eval-spec", ROOT, BINARY) == golden


@pytest.mark.parametrize(
    ("arg", "word"),
    [
        ("plain", "plain"),
        ("a b", '"a b"'),
        ('say "hi"', '"say \\"hi\\""'),
        ("back\\slash", '"back\\\\slash"'),
        ("100%", '"100%%"'),
        ("$HOME", '"$$HOME"'),
        ("two\nlines", '"two\\nlines"'),
        ("", '""'),
    ],
    ids=["bare", "space", "quote", "backslash", "specifier", "dollar", "newline", "empty"],
)
async def test_schedule_render_quotes_argv_for_systemd(arg: str, word: str) -> None:
    units = Schedule(doc="d", calendar="daily", steps=(("eval", arg),)).render("a", ROOT, BINARY)
    assert f"ExecStart={BINARY} eval {word}\n".encode() in units[SERVICE]


@pytest.mark.parametrize(
    ("root", "lines"),
    [
        (Path("/srv/e nous"), ("WorkingDirectory=/srv/e nous", 'Environment="TAXIS_NOUS=/srv/e nous"')),
        (Path("/srv/50%/$x"), ("WorkingDirectory=/srv/50%%/$x", 'Environment="TAXIS_NOUS=/srv/50%%/$x"')),
    ],
    ids=["space", "specifier"],
)
async def test_schedule_render_escapes_the_root(root: Path, lines: tuple[str, ...]) -> None:
    service = Schedule(doc="d", calendar="daily", steps=(("eval",),)).render("a", root, BINARY)[SERVICE].decode()
    assert all(f"{line}\n" in service for line in lines)


async def test_schedule_render_folds_the_doc_onto_one_line() -> None:
    units = Schedule(doc="two\n  lines 100%", calendar="daily", steps=(("eval",),)).render("a", ROOT, BINARY)
    assert b"Description=two lines 100%%\n" in units[SERVICE]


async def test_schedule_render_heads_both_files() -> None:
    units = SPEC.render("a", ROOT, BINARY)
    assert {name: body.decode().splitlines()[0] for name, body in units.items()} == {SERVICE: HEADER, TIMER: HEADER}


@pytest.mark.parametrize(
    ("name", "ident"),
    [("taxis-eval-spec.service", "eval-spec"), ("taxis-a.b.timer", "a.b")],
    ids=["service", "dotted"],
)
async def test_schedule_kind_ident(name: str, ident: str) -> None:
    assert ScheduleKind.ident(name) == ident


SAME = {SERVICE: b"s", TIMER: b"t"}


@pytest.mark.parametrize(
    ("want", "have", "action"),
    [
        (SAME, {}, ScheduleAction.CREATE),
        (SAME, SAME, ScheduleAction.KEEP),
        (SAME, {SERVICE: b"old", TIMER: b"t"}, ScheduleAction.UPDATE),
        (SAME, {SERVICE: b"s"}, ScheduleAction.UPDATE),
        ({}, SAME, ScheduleAction.REMOVE),
        ({}, {}, ScheduleAction.KEEP),
    ],
    ids=["create", "keep", "update", "partial", "remove", "off"],
)
async def test_schedule_plan_diff_per_id(
    want: dict[str, bytes], have: dict[str, bytes], action: ScheduleAction
) -> None:
    assert SchedulePlan.diff(want, have, ("a",)).steps == (ScheduleStep(id="a", action=action),)


async def test_schedule_plan_diff_orders_declared_then_orphans() -> None:
    have = {"taxis-z.timer": b"t", "taxis-b.service": b"s", TIMER: b"t"}
    plan = SchedulePlan.diff({}, have, ("y", "a"))
    assert [(step.id, step.action) for step in plan.steps] == [
        ("y", ScheduleAction.KEEP),
        ("a", ScheduleAction.REMOVE),
        ("b", ScheduleAction.REMOVE),
        ("z", ScheduleAction.REMOVE),
    ]
