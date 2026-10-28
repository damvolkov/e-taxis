"""tests/unit/e_taxis/runtime/launcher: `--nous` filled before the command runs — from any shell, no flag typed."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("tokens", "shown"),
    [(("transpile", "check", "--worktree"), "2 signal"), (("workflow", "list"), "converge")],
    ids=["transpile-check", "workflow-list"],
)
def test_launcher_locates_the_checkout_it_runs_in(
    taxis, monkeypatch: pytest.MonkeyPatch, checkout: Path, tokens: tuple[str, ...], shown: str
) -> None:
    monkeypatch.chdir(checkout / "core")
    code, out, _ = taxis(*tokens)
    assert (code, shown in out) == (0, True)


def test_launcher_locates_the_sibling_from_another_repo(
    taxis, monkeypatch: pytest.MonkeyPatch, checkout: Path, sibling: Path
) -> None:
    monkeypatch.chdir(sibling)
    code, out, _ = taxis("workflow", "list")
    assert (code, "converge" in out) == (0, True)


def test_launcher_explicit_invalid_exits_31(taxis, tmp_path: Path) -> None:
    code, _, err = taxis("transpile", "check", "--nous", str(tmp_path), "--worktree")
    assert code == 31
    assert "lacks" in err


def test_launcher_profile_is_the_source_no_ladder(taxis, monkeypatch: pytest.MonkeyPatch, catalog_root: Path) -> None:
    monkeypatch.setenv("TAXIS_CATALOG", str(catalog_root))
    code, _, err = taxis("plan", "--target", "opencode", "--profile", "house")
    assert code == 7
    assert "e-nous" not in err


def test_launcher_no_source_no_checkout_exits_31(taxis, monkeypatch: pytest.MonkeyPatch, catalog_root: Path) -> None:
    monkeypatch.setenv("TAXIS_CATALOG", str(catalog_root))
    code, _, err = taxis("plan", "--target", "opencode")
    assert code == 31
    assert "TAXIS_NOUS" in err
