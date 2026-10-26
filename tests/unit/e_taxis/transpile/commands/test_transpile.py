"""tests/unit/e_taxis/transpile/commands/transpile: `taxis transpile check` — clean exits 0, a break exits 20, JSON parses."""

from typing import TYPE_CHECKING, Any

import msgspec

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_transpile_check_clean_checkout_exits_zero(taxis, nous_root: Path) -> None:
    code, out, _ = taxis("transpile", "check", "--nous", str(nous_root), "--worktree")
    assert code == 0
    assert "0 blocking · 3 signal" in out


def test_transpile_check_blocking_finding_exits_twenty(
    taxis, nous_root: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit("specs/nomos/hermes.yaml", lambda s: s["map"]["config"]["unmapped"].pop("tools.calls"))
    code, out, err = taxis("transpile", "check", "--nous", str(nous_root), "--worktree")
    assert code == 20
    assert "tools.calls" in out
    assert "1 blocking finding" in err


def test_transpile_check_json_is_the_report(taxis, nous_git: Path) -> None:
    code, out, _ = taxis("transpile", "check", "--nous", str(nous_git), "--json")
    report = msgspec.json.decode(out)
    assert code == 0
    assert report["stamp"]["model"] == "2.0"
    assert len(report["stamp"]["commit"]) == 40
