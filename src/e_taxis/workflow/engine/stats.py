"""engine.stats: interval estimates for what the heuristic nodes measure — pure, seeded, stdlib only.

`interval_wilson` bounds a pass *proportion* (the routing probe): a mean ± deviation is undefined at 0 and 1 at the
small N a run affords and leaves [0, 1]; Wilson stays inside and never collapses on a clean sweep. It assumes
independent trials, and repeats of one case are correlated, so read it as a floor on the uncertainty.
`interval_bootstrap` bounds a paired delta (the effect A/B): seeds are averaged per task first — the task is the
independent cluster and the only unit resampled — and the generator is seeded, so one ledger yields one interval.
numpy is not a dependency: the data is a few dozen tasks, ten thousand draws of them is milliseconds in pure Python."""

import random
from math import sqrt
from statistics import fmean
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

##### DEFAULTS #####
Z95: float = 1.959963984540054


##### UTILITIES #####
def interval_wilson(passes: int, total: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval of `passes`/`total`, as (low, high) in [0, 1]; (0, 0) with nothing measured."""
    match total > 0:
        case False:
            return (0.0, 0.0)
        case _:
            rate, square = passes / total, z * z / total
            center = (rate + square / 2) / (1 + square)
            spread = z * sqrt(rate * (1 - rate) / total + square / (4 * total)) / (1 + square)
            return (max(0.0, center - spread), min(1.0, center + spread))


def quantile_stats(ordered: Sequence[float], share: float) -> float:
    """The `share` quantile of sorted values, linearly interpolated (numpy's default)."""
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def interval_bootstrap(
    base: Sequence[Sequence[float]], candidate: Sequence[Sequence[float]], boot: int, alpha: float, seed: int = 0
) -> tuple[float, float, float]:
    """(mean paired delta, low, high): `base` and `candidate` are task x seed scores on the same tasks, in order."""
    deltas = [fmean(after) - fmean(before) for before, after in zip(base, candidate, strict=True)]
    draw = random.Random(seed)  # noqa: S311 — a reproducible resample, not a secret
    means = sorted(fmean(draw.choices(deltas, k=len(deltas))) for _ in range(boot))
    return fmean(deltas), quantile_stats(means, alpha / 2), quantile_stats(means, 1 - alpha / 2)
