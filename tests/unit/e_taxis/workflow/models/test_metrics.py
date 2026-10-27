"""tests/unit/e_taxis/workflow/models/metrics: the heuristic readings say themselves in one report line."""

from e_taxis.workflow.models.metrics import ActivationMetrics, EffectMetrics, Interval, Score


async def test_metrics_activation_summary() -> None:
    metrics = ActivationMetrics(
        tree="base",
        mode="activation",
        backend="opencode",
        passed=1,
        total=2,
        rate=75.0,
        interval=Interval(30.1, 95.4),
        recall=(1, 1),
        precision=(0, 1),
        unmeasured=0,
        failures=("monta un makefile",),
    )
    assert metrics.summary == (
        "base activation on opencode: 1/2 cases · 75.0% [30-95] · recall 1/1 · precision 0/1 · 0 unmeasured"
        "\n      ✗ monta un makefile"
    )


async def test_metrics_effect_summary() -> None:
    metrics = EffectMetrics(
        split="test",
        tasks=6,
        seeds=3,
        base=Score(0.5, 0.6),
        candidate=Score(0.75, 0.8),
        delta=Score(0.25, 0.2),
        hard=Interval(0.1, 0.4),
        soft=Interval(0.05, 0.3),
        mode="value",
    )
    assert metrics.summary == ("value on test 6x3: soft 0.60→0.80 [+0.050, +0.300] · hard 0.50→0.75 [+0.100, +0.400]")
