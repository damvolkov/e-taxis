"""Unit tests for the three-way plan: which side moved, and whether applying would destroy.

The question a two-way diff cannot answer. Every test here builds the three points
explicitly — base, live, render — and asserts the verdict, never the comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from ops.models.entity import Backend
from ops.transpiler.history.classify import Classifier
from ops.transpiler.history.plan import Planner
from ops.transpiler.history.store import Store
from ops.transpiler.history.view import render
from ops.transpiler.render import Transpiler
from tests.unit.ops.transpiler.history.conftest import write

SKILL = "skills/data-py-cache/SKILL.md"
BASE = "---\nname: data-py-cache\ndescription: the original\n---\n\n# data-py-cache\n\nrule one\n"
#: What the fake merge never drops from a live file.
KEPT = "\n## Kept\n"
#: The shipped specs: the fake paths the tests dictate must land on real routes.
SPECS = Classifier(Transpiler())


class FakeTranspiler:
    """A transpiler whose render is dictated by the test, over a real output tree."""

    def __init__(self, out: Path, files: dict[str, str]) -> None:
        self.out = out
        self.backend = Backend.OPENCODE
        self.files: Mapping[Path, str] = {out / rel: text for rel, text in files.items()}

    def owned(self, path: Path, text: str) -> str:
        return text

    def merged(self, path: Path, text: str) -> str:
        live = path.read_text() if path.is_file() else ""
        return text + live.partition(KEPT)[1] + live.partition(KEPT)[2] if KEPT in live else text


@pytest.fixture
def planted(tmp_path: Path) -> tuple[Path, Store]:
    """A harness holding one skill, with that state already recorded as the base."""
    out = tmp_path / "ecoder"
    write(out, {SKILL: BASE})
    store = Store(out, tmp_path / "state.git")
    store.initialise()
    store.snapshot("export")
    return out, store


def _plan(planted: tuple[Path, Store], render: dict[str, str]):
    out, store = planted
    return Planner(render=FakeTranspiler(out, render), store=store, classifier=SPECS).plan()


# ------------------------------------------------------------------ verdicts
def test_nothing_moved_is_an_empty_plan(planted: tuple[Path, Store]) -> None:
    assert _plan(planted, {SKILL: BASE}).empty


def test_core_moved_alone_is_safe_to_apply(planted: tuple[Path, Store]) -> None:
    plan = _plan(planted, {SKILL: BASE.replace("rule one", "rule one, rewritten")})
    assert [move.direction for move in plan.moves] == ["core"]
    assert plan.destructive == ()


def test_the_harness_moved_alone_and_applying_would_destroy_it(planted: tuple[Path, Store]) -> None:
    """The live case: research landed straight in the harness and core knows nothing of it."""
    out, _ = planted
    write(out, {SKILL: BASE.replace("rule one", "rule one, and a finding only the harness has")})
    plan = _plan(planted, {SKILL: BASE})
    assert [move.direction for move in plan.moves] == ["harness"]
    assert len(plan.destructive) == 1


def test_both_moved_is_a_divergence(planted: tuple[Path, Store]) -> None:
    out, _ = planted
    write(out, {SKILL: BASE.replace("rule one", "the harness wrote this")})
    plan = _plan(planted, {SKILL: BASE.replace("the original", "core wrote this")})
    assert [move.direction for move in plan.moves] == ["diverged"]
    assert plan.destructive


def test_without_a_base_no_direction_can_be_claimed(tmp_path: Path) -> None:
    """A store with no snapshot cannot say who moved; it must say so rather than guess."""
    out = tmp_path / "ecoder"
    write(out, {SKILL: BASE})
    store = Store(out, tmp_path / "state.git")
    store.initialise()
    plan = Planner(
        render=FakeTranspiler(out, {SKILL: BASE.replace("rule one", "other")}), store=store, classifier=SPECS
    ).plan()
    assert [move.direction for move in plan.moves] == ["unbased"]


def test_a_runtime_tree_the_base_recorded_is_not_judged(tmp_path: Path) -> None:
    """A base sealed before a tree was declared third-party still holds it; no spec claims it, so it is skipped."""
    out = tmp_path / "ecoder"
    write(out, {SKILL: BASE, "skills/.trash/1-a/SKILL.md": "gone\n"})
    store = Store(out, tmp_path / "state.git")
    store.initialise()
    store.snapshot("export")
    assert Planner(render=FakeTranspiler(out, {SKILL: BASE}), store=store, classifier=SPECS).plan().empty


def test_what_the_merge_keeps_from_live_is_never_lost(planted: tuple[Path, Store]) -> None:
    """The harness added what the core does not declare; the merge carries it, so applying loses nothing."""
    out, _ = planted
    (out / SKILL).write_text(f"{BASE}{KEPT}mine\n")
    assert _plan(planted, {SKILL: BASE}).empty


# -------------------------------------------------------------------- shape
def test_the_plan_grades_what_it_reports(planted: tuple[Path, Store]) -> None:
    plan = _plan(planted, {SKILL: BASE.replace("the original", "a new description")})
    assert plan.moves[0].change.grade == "routing"
    assert plan.bump == "minor"


def test_a_body_only_change_bumps_minor_as_guidance(planted: tuple[Path, Store]) -> None:
    plan = _plan(planted, {SKILL: BASE.replace("rule one", "rule one, rewritten")})
    assert plan.moves[0].change.grade == "guidance" and plan.bump == "minor"


def test_a_new_entity_is_reported_as_added(planted: tuple[Path, Store]) -> None:
    plan = _plan(planted, {SKILL: BASE, "agents/scout.md": "---\ndescription: scouts\n---\n\nprompt\n"})
    added = [move for move in plan.moves if move.change.kind == "added"]
    assert len(added) == 1 and added[0].change.grade == "surface"


def test_a_vanished_entity_is_reported_as_removed(planted: tuple[Path, Store]) -> None:
    plan = _plan(planted, {})
    assert [move.change.kind for move in plan.moves] == ["removed"]
    assert plan.bump == "major"


def test_the_plan_names_the_base_it_compared_against(planted: tuple[Path, Store]) -> None:
    _, store = planted
    plan = _plan(planted, {SKILL: BASE})
    head = store.head()
    assert head is not None and plan.base is not None and plan.base.commit == head.commit


def test_the_plan_carries_the_three_points(planted: tuple[Path, Store]) -> None:
    out, _ = planted
    plan = _plan(planted, {SKILL: BASE})
    assert plan.settled == 1 and plan.live == str(out) and "opencode" in plan.core


# -------------------------------------------------------------------- sides
def test_a_core_move_carries_the_two_versions_the_export_would_apply(planted: tuple[Path, Store]) -> None:
    """`--diff` shows model data, not view invention: apply and the changelog read the same pair."""
    plan = _plan(planted, {SKILL: BASE.replace("rule one", "rule one, rewritten")})
    move = plan.moves[0]
    assert move.before == BASE and "rewritten" in move.after and move.sides == ("live", "render")
    assert "-rule one" in move.diff() and "+rule one, rewritten" in move.diff()


def test_a_harness_move_carries_what_the_harness_did_to_the_recorded_state(planted: tuple[Path, Store]) -> None:
    out, _ = planted
    write(out, {SKILL: BASE.replace("rule one", "harness finding")})
    move = _plan(planted, {SKILL: BASE}).moves[0]
    assert move.sides == ("recorded", "live") and "harness finding" in move.after and "rewritten" not in move.after


# --------------------------------------------------------------------- specs
def test_plan_names_a_spec_that_moved_without_moving_the_render(planted: tuple[Path, Store], tmp_path: Path) -> None:
    out, store = planted
    specs = tmp_path / "repo" / "specs"
    write(specs, {"opencode/config.yaml": "release: '2026.09.23'\n"})
    store.seal(specs)
    write(specs, {"opencode/config.yaml": "release: '2026.10.01'\n"})
    plan = Planner(render=FakeTranspiler(out, {SKILL: BASE}), store=store, classifier=SPECS, specs=specs).plan()
    assert plan.empty and plan.sealed and plan.unsealed
    assert [(c.path, c.kind) for c in plan.specs] == [("specs/opencode/config.yaml", "changed")]
    assert "render unchanged · apply only seals them" in render(plan, "text")


def test_plan_on_an_unsealed_base_says_so(planted: tuple[Path, Store], tmp_path: Path) -> None:
    out, store = planted
    specs = tmp_path / "repo" / "specs"
    write(specs, {"opencode/config.yaml": "x\n"})
    plan = Planner(render=FakeTranspiler(out, {SKILL: BASE}), store=store, classifier=SPECS, specs=specs).plan()
    assert not plan.sealed and plan.specs == () and "not sealed" in render(plan, "text")
