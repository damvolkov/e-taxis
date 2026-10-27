"""tests/unit/e_taxis/workflow/engine/stats: Wilson stays inside [0, 1] and never collapses on a sweep; the bootstrap
is seeded, resamples whole tasks, and centres on the mean paired delta."""

import pytest

from e_taxis.workflow.engine.stats import interval_bootstrap, interval_wilson, quantile_stats


@pytest.mark.parametrize(
    ("passes", "total", "low", "high"),
    [(0, 0, 0.0, 0.0), (10, 10, 0.7225, 1.0), (0, 10, 0.0, 0.2775), (5, 10, 0.2366, 0.7634)],
    ids=["nothing", "sweep", "none", "half"],
)
async def test_stats_wilson(passes: int, total: int, low: float, high: float) -> None:
    assert interval_wilson(passes, total) == pytest.approx((low, high), abs=1e-4)


async def test_stats_quantile_interpolates() -> None:
    assert (quantile_stats([0.0, 1.0, 2.0, 3.0], 0.5), quantile_stats([0.0, 1.0], 1.0)) == (1.5, 1.0)


async def test_stats_bootstrap_identical_arms_is_zero() -> None:
    grid = [[1.0, 0.0], [0.5, 0.5], [0.0, 0.0]]
    assert interval_bootstrap(grid, grid, 500, 0.05) == (0.0, 0.0, 0.0)


async def test_stats_bootstrap_is_seeded_and_brackets_the_delta() -> None:
    base, candidate = [[0.0, 0.0], [0.5, 0.5], [0.0, 1.0]], [[1.0, 1.0], [1.0, 0.5], [0.5, 1.0]]
    first = interval_bootstrap(base, candidate, 2000, 0.05)
    mean, low, high = first
    assert first == interval_bootstrap(base, candidate, 2000, 0.05)
    assert (mean, low <= mean <= high, low > 0) == (pytest.approx(0.5), True, True)
