"""tests/unit/e_taxis/workflow/models/case: a query case holds per mode on its own fields — loads, opens, or the
markers recited — and an unanswered session is never measured."""

import pytest

from e_taxis.workflow.models.case import ProbeMode, ProbeResult, QueryCase

CASE = QueryCase(
    prompt="p",
    expect=frozenset({"algo"}),
    reject=frozenset({"make"}),
    reads=frozenset({"algo/lib.md"}),
    markers=frozenset({"Big-O first"}),
    not_loaded=frozenset({"algo"}),
)


@pytest.mark.parametrize(
    ("mode", "result", "holds"),
    [
        (ProbeMode.ACTIVATION, ProbeResult(loaded=frozenset({"algo"})), True),
        (ProbeMode.ACTIVATION, ProbeResult(loaded=frozenset({"algo", "make"})), False),
        (ProbeMode.NAVIGATION, ProbeResult(opened=frozenset({"algo/lib.md"})), True),
        (ProbeMode.NAVIGATION, ProbeResult(), False),
        (ProbeMode.PRELOAD, ProbeResult(text="**big-O  first!**"), True),
        (ProbeMode.PRELOAD, ProbeResult(text="big-O first", loaded=frozenset({"algo"})), False),
    ],
    ids=["loads", "loads-rejected", "opens", "opens-nothing", "recites", "recites-but-loads"],
)
async def test_case_holds(mode: ProbeMode, result: ProbeResult, holds: bool) -> None:
    assert CASE.holds(mode, result) is holds


async def test_case_positive_and_silent() -> None:
    negative = QueryCase(prompt="n", reject=frozenset({"algo"}))
    assert (CASE.positive(ProbeMode.ACTIVATION), negative.positive(ProbeMode.ACTIVATION)) == (True, False)
    assert (negative.asserts(ProbeMode.ACTIVATION), negative.asserts(ProbeMode.NAVIGATION)) == (True, False)


async def test_case_unanswered_is_unmeasured() -> None:
    assert (ProbeResult().measured, ProbeResult(error="429").measured) == (True, False)
