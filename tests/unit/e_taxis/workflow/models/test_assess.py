"""tests/unit/e_taxis/workflow/models/assess: a plan names one candidate and one baseline; answers forbid strays."""

from typing import Any

import msgspec
import pytest

from e_taxis.workflow.models.assess import Fetched, Plan, Role, Upstream

ARM = {"install": [], "run": ["echo 1"]}
PLAN = {
    "incumbent": "x",
    "overlap": "replaces",
    "hypothesis": "h",
    "metric": "seconds",
    "threshold": 0,
    "higher_is_better": False,
    "cases": ["a"],
    "n": 2,
    "cache": "warm",
    "landing": "l",
}


@pytest.mark.parametrize(
    ("arms", "baseline"),
    [
        ([{"name": "c", "role": "candidate"}, {"name": "i", "role": "incumbent"}], ("i", Role.INCUMBENT)),
        ([{"name": "e", "role": "empty"}, {"name": "c", "role": "candidate"}], ("e", Role.EMPTY)),
    ],
    ids=["incumbent", "empty"],
)
async def test_assess_plan_names_its_sides(arms: list[dict[str, Any]], baseline: tuple[str, Role]) -> None:
    plan = msgspec.convert({**PLAN, "arms": [{**ARM, **arm} for arm in arms]}, Plan)
    assert (plan.candidate.role, (plan.baseline.name, plan.baseline.role)) == (Role.CANDIDATE, baseline)


@pytest.mark.parametrize(
    ("arms", "extra", "match"),
    [
        ([{"name": "a", "role": "candidate"}, {"name": "a", "role": "empty"}], {}, r"arm names repeat: \['a'\]"),
        ([{"name": "a", "role": "candidate"}, {"name": "b", "role": "candidate"}], {}, "exactly one candidate arm"),
        ([{"name": "a", "role": "candidate"}], {}, "exactly one candidate arm"),
        ([{"name": "a b", "role": "candidate"}], {}, "matching regex"),
        ([], {"n": 0}, ">= 1"),
        ([], {"surprise": 1}, "unknown field"),
    ],
    ids=["repeat", "two-candidates", "no-baseline", "bad-name", "n", "stray"],
)
async def test_assess_plan_refuses(arms: list[dict[str, Any]], extra: dict[str, Any], match: str) -> None:
    with pytest.raises(msgspec.ValidationError, match=match):
        msgspec.convert({**PLAN, **extra, "arms": [{**ARM, **arm} for arm in arms]}, Plan)


async def test_assess_upstream_forbids_strays() -> None:
    with pytest.raises(msgspec.ValidationError, match="unknown field"):
        msgspec.convert({"what": "w", "install": [], "requires": [], "claims": [], "docs": [], "x": 1}, Upstream)


@pytest.mark.parametrize(("status", "ok"), [(200, True), (299, True), (0, False), (404, False)])
async def test_assess_fetched_ok(status: int, ok: bool) -> None:
    assert Fetched(url="u", status=status).ok is ok
