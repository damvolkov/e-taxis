"""tests/unit/e_taxis/workflow/assess/stats: the paired interval against the threshold, in the plan's direction, and
`not measured` with its reason whenever no pair exists."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.workflow.assess.stats import AssessStats
from e_taxis.workflow.models.assess import ArmSamples, Outcome, Role, Sample, Samples

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.assess import Plan


@pytest.mark.parametrize(
    ("fast", "slow", "higher", "outcome"),
    [
        ([1.0, 1.1, 0.9, 1.0], [3.0, 3.2, 2.9, 3.1], False, Outcome.BETTER),
        ([1.0, 1.1, 0.9, 1.0], [3.0, 3.2, 2.9, 3.1], True, Outcome.WORSE),
        ([3.0, 3.1, 2.9, 3.0], [3.1, 3.0, 3.0, 2.9], False, Outcome.SAME),
        ([5.0, 5.2, 4.9, 5.1], [3.0, 3.2, 2.9, 3.1], False, Outcome.WORSE),
    ],
    ids=["lower-better", "higher-worse", "inside-threshold", "lower-worse"],
)
async def test_stats_compare_outcome(
    plan: Callable[..., Plan],
    samples: Callable[..., Samples],
    fast: list[float],
    slow: list[float],
    higher: bool,
    outcome: Outcome,
) -> None:
    found = AssessStats(resamples=2000).compare(plan(higher_is_better=higher), samples(fast, slow))
    assert (found.outcome, found.pairs, found.resamples, found.confidence) == (outcome, 4, 2000, 0.95)
    assert found.low is not None
    assert found.high is not None
    assert found.low <= (found.mean or 0) <= found.high


async def test_stats_compare_is_seeded(plan: Callable[..., Plan], samples: Callable[..., Samples]) -> None:
    measured = samples([1.0, 2.0, 1.5, 0.5, 1.2], [3.0, 2.5, 3.5, 2.0, 2.8])
    first, again = [AssessStats().compare(plan(seed=5), measured) for _ in range(2)]
    assert (first.low, first.high, first.mean) == (again.low, again.high, again.mean)
    assert first.mean == pytest.approx(-1.52)


async def test_stats_compare_pairs_only_runs_both_measured(
    plan: Callable[..., Plan], samples: Callable[..., Samples]
) -> None:
    found = AssessStats(resamples=100).compare(plan(), samples([1.0, None, 1.0], [2.0, 2.0, None]))
    assert (found.pairs, found.mean) == (1, -1.0)
    assert found.secondary["runs"] == "fast 2/3 measured · slow 2/3 measured"


async def test_stats_compare_describes_the_secondary(plan: Callable[..., Plan]) -> None:
    arms = (
        ArmSamples(
            name="fast",
            role=Role.CANDIDATE,
            installed=True,
            samples=(Sample(case="a", rep=0, at=0, metric=1.0, secondary={"rss": 10.0}),),
        ),
        ArmSamples(
            name="slow", role=Role.INCUMBENT, installed=True, samples=(Sample(case="a", rep=0, at=1, metric=2.0),)
        ),
    )
    found = AssessStats(resamples=10).compare(plan(secondary=("tokens",)), Samples(arms=arms, warmup=0))
    assert found.secondary == {
        "tokens": "fast not reported · slow not reported",
        "rss": "fast 10 (n=1) · slow not reported",
        "runs": "fast 1/1 measured · slow 1/1 measured",
    }


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"reason": "bench=false: judged on desk evidence", "arms": ()}, "bench=false: judged on desk evidence"),
        ({"arms": ()}, "fast never ran; slow never ran"),
        ("uninstalled", "slow not installed (exit 1: no)"),
        ("empty", "no pair measured by both arms"),
    ],
    ids=["skipped", "never-ran", "uninstalled", "no-pair"],
)
async def test_stats_compare_not_measured(
    plan: Callable[..., Plan], samples: Callable[..., Samples], change: object, reason: str
) -> None:
    base = samples([1.0], [None])
    match change:
        case dict() as fields:
            measured = msgspec.structs.replace(base, **fields)
        case "uninstalled":
            broken = msgspec.structs.replace(base.arms[1], installed=False, error="exit 1: no", samples=())
            measured = msgspec.structs.replace(base, arms=(base.arms[0], broken))
        case _:
            measured = base
    found = AssessStats().compare(plan(), measured)
    assert (found.outcome, found.reason, found.low, found.pairs) == (Outcome.UNMEASURED, reason, None, 0)
