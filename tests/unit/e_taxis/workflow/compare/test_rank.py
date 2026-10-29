"""tests/unit/e_taxis/workflow/compare/rank: one rubric — compiled first, maintained over popular, stars a tie-breaker,
an unknown never a strength — and the best rival kept only past the margin."""

import datetime as dt
from typing import TYPE_CHECKING

from e_taxis.workflow.compare.rank import CompareRank
from e_taxis.workflow.models.compare import Healths

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.compare import Rivals, Vital

NOW = dt.datetime(2026, 10, 29, tzinfo=dt.UTC)
FRESH = {"last_release": "2026-10-28T00:00:00+00:00", "releases_per_year": 12.0, "license": "MIT"}


async def test_rank_keeps_the_best_rival_past_the_margin(rivals: Rivals, vital: Callable[..., Vital]) -> None:
    healths = Healths(
        measured_at="x",
        subjects=(
            vital("msgspec", **FRESH),
            vital("orjson", rust=True, stars=10, **FRESH),
            vital("pydantic-core", rust=True, stars=99, **FRESH),
            vital("wreq", rust=True, license="GPL-3.0", scorecard=8.0, dependents=99, downloads_month=10**6),
        ),
    )
    shortlist = CompareRank(NOW).rank(rivals, healths)
    msgspec_contest, wreq_contest = shortlist.contests
    assert [score.name for score in msgspec_contest.scores] == ["msgspec", "pydantic-core", "orjson"]
    assert msgspec_contest.rival == "pydantic-core"
    assert msgspec_contest.scores[0].unmeasured == ("dependents", "downloads", "scorecard")
    assert (wreq_contest.rival, wreq_contest.reason) == ("", "kept by the rubric: no rival named")
    assert wreq_contest.scores[0].terms["licence"] == 0.0


async def test_rank_keeps_an_incumbent_no_rival_beats(rivals: Rivals, vital: Callable[..., Vital]) -> None:
    healths = Healths(
        measured_at="x",
        subjects=(
            vital("msgspec", rust=True, **FRESH),
            vital("orjson", rust=True, **FRESH),
            vital("pydantic-core", **FRESH),
            vital("wreq"),
        ),
    )
    contest = CompareRank(NOW).rank(rivals, healths).contests[0]
    assert (contest.rival, contest.reason.startswith("kept by the rubric: orjson scores")) == ("", True)
