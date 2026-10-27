"""tests/unit/e_taxis/workflow/commands/enhance: `taxis enhance run | graph | promote` through the real app.

`promote` is a human command on purpose: refused in an agent's session (`TAXIS_HEADLESS`, `OPS_GLOBAL__HEADLESS`)
even with a mandate, refused without a terminal or a mandate, and with one it applies the run's patches."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.workflow.commands.enhance import human_confirm, human_guard
from e_taxis.workflow.models.error import HumanError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

type Taxis = Callable[..., tuple[int, str, str]]

LIB = "core/tekton/skills/algo-py-core/references/lib.md"


def test_enhance_run_prints_the_verdict(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    code, out, _ = taxis("enhance", "run", "skill", "algo-py-core", "--nous", str(plane_nous), "--manual")
    assert code == 0
    assert "algo-py-core            settled" in out


def test_enhance_run_without_reason_exits_28(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    code, _, err = taxis("enhance", "run", "skill", "algo-py-core", "--nous", str(plane_nous))
    assert code == 28
    assert "needs a reason" in err


def test_enhance_graph_prints_the_enhancer(taxis: Taxis, plane_deps: PlaneRun) -> None:
    code, out, _ = taxis("enhance", "graph", "skill")
    assert code == 0
    assert "security_candidate" in out


def test_enhance_promote_without_a_human_exits_29(
    taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TAXIS_HUMAN", raising=False)
    code, _, err = taxis("enhance", "promote", "--nous", str(enhanced), "--yes")
    assert code == 29
    assert "no terminal" in err


def test_enhance_promote_with_the_mandate_applies(
    taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    code, out, _ = taxis("enhance", "promote", "--nous", str(enhanced), "--yes", "--ids", "algo-py-core")
    assert code == 0
    assert "applied  algo-py-core" in out
    assert (enhanced / LIB).read_text().endswith("Promoted depth.\n")


def test_enhance_promote_twice_finds_it_already_there(
    taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    taxis("enhance", "promote", "--nous", str(enhanced), "--yes", "--all-verdicts")
    code, out, _ = taxis("enhance", "promote", "--nous", str(enhanced), "--yes", "--all-verdicts")
    assert code == 0
    assert "already  algo-py-core" in out


def test_enhance_promote_refuses_a_patch_that_does_not_apply(
    taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    (enhanced / LIB).write_text("rewritten by hand\n")
    code, out, err = taxis("enhance", "promote", "--nous", str(enhanced), "--yes", "--all-verdicts")
    assert code == 1
    assert "refused  algo-py-core: patch does not apply" in out
    assert "1 patch(es) refused" in err


def test_enhance_promote_refuses_a_moved_head(taxis: Taxis, moved: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    code, _, err = taxis("enhance", "promote", "--nous", str(moved), "--yes")
    assert code == 30
    assert "run the enhancement again" in err


def test_enhance_promote_refuses_an_unknown_id(taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    code, _, err = taxis("enhance", "promote", "--nous", str(enhanced), "--yes", "--ids", "ghost")
    assert code == 27
    assert "no verdict for ghost" in err


def test_enhance_promote_unconfirmed_writes_nothing(
    taxis: Taxis, enhanced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAXIS_HUMAN", "1")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    code, _, err = taxis("enhance", "promote", "--nous", str(enhanced))
    assert code == 1
    assert "aborted" in err
    assert not (enhanced / LIB).read_text().endswith("Promoted depth.\n")


@pytest.mark.parametrize(
    ("env", "terminal", "message"),
    [
        ({"TAXIS_HEADLESS": "1", "TAXIS_HUMAN": "1"}, True, "an agent drives"),
        ({"OPS_GLOBAL__HEADLESS": "1"}, True, "an agent drives"),
        ({}, False, "no terminal"),
    ],
    ids=["headless-with-mandate", "ops-headless", "no-terminal"],
)
async def test_enhance_human_guard_refuses(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], terminal: bool, message: str
) -> None:
    _ = [monkeypatch.delenv(name, raising=False) for name in ("TAXIS_HEADLESS", "OPS_GLOBAL__HEADLESS", "TAXIS_HUMAN")]
    _ = [monkeypatch.setenv(name, value) for name, value in env.items()]
    with pytest.raises(HumanError, match=message):
        human_guard(TaxisSettings(), terminal=terminal)


async def test_enhance_human_guard_lets_a_terminal_through(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = [monkeypatch.delenv(name, raising=False) for name in ("TAXIS_HEADLESS", "OPS_GLOBAL__HEADLESS", "TAXIS_HUMAN")]
    assert human_guard(TaxisSettings(), terminal=True) is None


@pytest.mark.parametrize(("said", "expected"), [("y", True), ("YES ", True), ("", False)], ids=["y", "yes", "empty"])
async def test_enhance_human_confirm_reads_the_answer(
    monkeypatch: pytest.MonkeyPatch, said: str, expected: bool
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: said)
    assert await human_confirm("go?", yes=False) is expected


async def test_enhance_human_confirm_closed_stdin_is_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def closed(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", closed)
    assert await human_confirm("go?", yes=False) is False
    assert await human_confirm("go?", yes=True) is True
