"""tests/unit/e_taxis/commands/stack: `plan` and `verify` from a profile or an e-nous checkout."""

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from pathlib import Path


def test_stack_plan_profile_fails_on_unknown_and_blocked(taxis, on_catalog) -> None:
    code, out, err = taxis("plan", "--target", "claudecode", "--profile", "house")
    assert code == 7
    assert all(word in out for word in ("alpha", "skip", "install", "blocked", "unknown"))
    assert "2 part(s) cannot be planned: delta, ghost" in err


def test_stack_plan_nous_json(taxis, on_catalog, nous_root: Path) -> None:
    code, out, _ = taxis("plan", "--target", "opencode", "--nous", str(nous_root), "--json")
    assert code == 0
    plan = msgspec.json.decode(out)
    assert (plan["target"], [(step["id"], step["action"]) for step in plan["steps"]]) == (
        "opencode",
        [("alpha", "skip"), ("gamma", "skip")],
    )


def test_stack_plan_needs_exactly_one_source(taxis, on_catalog) -> None:
    code, _, err = taxis("plan", "--target", "claudecode")
    assert code == 6
    assert "exactly one source" in err


def test_stack_verify_profile_fails_on_a_failed_part(taxis, on_catalog) -> None:
    code, out, err = taxis("verify", "--target", "claudecode", "--profile", "house")
    assert code == 8
    assert "pass" in out
    assert "2 part(s) failed verify: beta, ghost" in err


def test_stack_verify_nous_json_passes(taxis, on_catalog, nous_root: Path) -> None:
    code, out, _ = taxis("verify", "--target", "opencode", "--nous", str(nous_root), "--json")
    assert code == 0
    assert [result["passed"] for result in msgspec.json.decode(out)["results"]] == [True, True]
