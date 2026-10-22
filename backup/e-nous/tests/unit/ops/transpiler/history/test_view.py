"""Unit tests for the view: one model, three faces, and a form that never hides a zero.

The view is pure presentation over `Plan`, so the plans are built by hand here —
no store, no filesystem. What must hold: every entity is named even at rest, the
json is the changelog payload itself, and the three faces agree on the counts.
"""

from __future__ import annotations

import datetime as dt

import msgspec

from ops.models.entity import Entity
from ops.models.history import Change, Snapshot
from ops.transpiler.history.plan import Move, Plan
from ops.transpiler.history.view import render, summary

AT = dt.datetime(2026, 9, 28, 12, 0, tzinfo=dt.UTC)
BASE = Snapshot(commit="abc123def456", at=AT, reason="manual", note="history base", ref="refs/snapshots/x")
MOVE = Move(
    change=Change(
        entity=Entity.SKILL,
        id="data-py-cache",
        target="skills/data-py-cache/SKILL.md",
        kind="changed",
        grade="routing",
        pointers=("/description",),
        summary="data-py-cache: description",
    ),
    direction="harness",
    before="the original text\nsecond line\n",
    after="the new text\nsecond line\n",
)
SETTLED = Plan(moves=(), base=BASE, settled=186, live="/home/d/.config/ecoder", core="opencode (core)")
MOVED = Plan(moves=(MOVE,), bump="minor", base=BASE, settled=185, live="/home/d/.config/ecoder", core="opencode (core)")


# --------------------------------------------------------------------- table
def test_the_empty_form_still_names_every_entity() -> None:
    """A report that hides its zeros is how a diff tool lies."""
    printed = render(SETTLED, "table")
    assert "nothing to apply" in printed
    for entity in Entity:
        assert entity.value in printed
    assert "186 settled" in printed


def test_the_table_reports_the_move_and_its_cost() -> None:
    printed = render(MOVED, "table")
    assert "harness" in printed and "routing" in printed and "/description" not in printed  # slots: names, not pointers
    assert "description" in printed and "1 would lose work" in printed


# ---------------------------------------------------------------------- json
def test_the_json_is_the_payload_itself() -> None:
    """What the changelog will persist: decodable, complete, the same counts."""
    decoded = msgspec.json.decode(render(MOVED, "json").encode())
    assert decoded["bump"] == "minor" and decoded["settled"] == 185
    assert decoded["base"]["commit"] == "abc123def456"
    move = decoded["moves"][0]
    assert move["direction"] == "harness" and move["change"]["pointers"] == ["/description"]


def test_the_json_of_an_empty_plan_holds_an_empty_moves_list() -> None:
    assert msgspec.json.decode(render(SETTLED, "json").encode())["moves"] == []


# ---------------------------------------------------------------------- text
def test_text_and_table_and_json_agree_on_the_summary() -> None:
    expected = "1 to apply"
    assert all(expected in render(MOVED, face) for face in ("table", "text"))
    assert expected not in render(MOVED, "json")  # json carries fields, not prose


def test_text_shows_every_section_even_at_rest() -> None:
    printed = render(SETTLED, "text")
    assert "(0)" in printed and "—" in printed and "skill 0" in printed


# -------------------------------------------------------------------- banner
def test_the_banner_says_what_you_are_reading_before_the_numbers_scroll() -> None:
    assert render(SETTLED, "text").startswith("TRANSPILE PLAN")
    assert "TRANSPILE PLAN" in render(SETTLED, "table")
    assert "TRANSPILE PLAN" not in render(SETTLED, "json")  # the payload carries no prose


# ------------------------------------------------------------------ content
def test_content_mode_adds_the_hunks_under_the_stat() -> None:
    assert "@@" not in render(MOVED, "table")
    printed = render(MOVED, "table", content=True)
    assert "@@" in printed and "-the original text" in printed and "+the new text" in printed


def test_text_content_names_the_sides_the_move_carried() -> None:
    assert "── recorded → live · skills/data-py-cache/SKILL.md" in render(MOVED, "text", content=True)


def test_json_carries_the_versions_as_data_not_as_hunks() -> None:
    """The machine diffs `before`/`after` itself; `content` deliberately does not touch it."""
    decoded = msgspec.json.decode(render(MOVED, "json", content=True).encode())
    assert decoded == msgspec.json.decode(render(MOVED, "json").encode())
    assert decoded["moves"][0]["before"] == "the original text\nsecond line\n"


def test_summary_shows_every_target_side_by_side() -> None:
    out = summary({"opencode": MOVED, "openhuman": SETTLED})
    row = next(line for line in out.splitlines() if MOVE.change.entity.value in line)
    assert "opencode" in out and "openhuman" in out and "1" in row and "·" in row


def test_summary_with_nothing_moving_says_so() -> None:
    assert "nothing to apply" in summary({"opencode": SETTLED, "claudecode": SETTLED})
