"""tests/unit/e_taxis/workflow/compare/pairs: bench and stats per shortlisted pair, as radar-tech does one."""

import datetime as dt
from typing import TYPE_CHECKING

from e_taxis.workflow.assess.stats import AssessStats
from e_taxis.workflow.compare.bench import CompareBench
from e_taxis.workflow.compare.stats import CompareStats
from e_taxis.workflow.models.assess import Outcome, Samples
from e_taxis.workflow.models.compare import Benched, Migration, PairSamples, Plans, Weighed

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.assess import Plan

NOW = dt.datetime(2026, 10, 29, tzinfo=dt.UTC)


async def test_pairs_bench_and_stats_per_pair(plan: Callable[..., Plan], skipping) -> None:
    migration = Migration(files=("a.py",), changes=("swap",))
    plans = Plans(pairs=(Weighed(incumbent="msgspec", rival="orjson", plan=plan(), migration=migration),))
    samples = await CompareBench(skipping).run(plans, skip=True, now=NOW)
    stats = CompareStats(AssessStats()).compare(plans, samples)
    assert (skipping.skips, samples.pairs[0].rival) == ([True], "orjson")
    assert stats.pairs[0].stats.outcome is Outcome.UNMEASURED


async def test_pairs_stats_drop_a_pair_never_benched(plan: Callable[..., Plan]) -> None:
    migration = Migration(files=(), changes=())
    plans = Plans(pairs=(Weighed(incumbent="a", rival="b", plan=plan(), migration=migration),))
    other = PairSamples(pairs=(Benched(incumbent="x", rival="y", samples=Samples(arms=(), warmup=0)),))
    assert CompareStats(AssessStats()).compare(plans, other).pairs == ()
