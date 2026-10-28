"""tests/unit/e_taxis/workflow/assess/bench: arms installed and measured for real through the stand-in landrun —
sandboxes, interleaving, warm-ups, the metric contract, and every failure kept as a result."""

from collections import Counter
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.assess import bench as module
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.models.assess import Overlap, Role
from e_taxis.workflow.models.error import AssessError

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.assess import Arm, Plan
    from e_taxis.workflow.models.ports import LabPort

PATH = "/usr/bin:/bin"


async def test_bench_run_interleaves_and_discards_the_warmup(
    lab: LabPort, plan: Callable[..., Plan], arm: Callable[..., Arm], now: dt.datetime, tmp_path: Path
) -> None:
    arms = (
        arm("fast", Role.CANDIDATE, run=("echo 1",)),
        arm("slow", Role.INCUMBENT, run=("""echo '{"metric": 3, "rss": 10, "flag": true}'""",)),
    )
    found = await AssessBench(lab, path=PATH, limit=10, temp=tmp_path).run(
        plan(*arms, cases=("a", "b"), n=2, warmup=1, seed=3), skip=False, now=now
    )
    fast, slow = found.arms
    assert (found.warmup, found.seed, found.measured_at) == (1, 3, now.isoformat())
    assert [(s.case, s.rep, s.metric) for s in fast.samples] == [
        ("a", 1, 1.0),
        ("b", 1, 1.0),
        ("a", 2, 1.0),
        ("b", 2, 1.0),
    ]
    assert {s.metric for s in slow.samples} == {3.0}
    assert slow.samples[0].secondary == {"rss": 10.0}
    rounds = Counter(s.at // 2 for s in (*fast.samples, *slow.samples))
    assert rounds == {2: 2, 3: 2, 4: 2, 5: 2}
    assert found.machine is not None
    assert found.machine.cores >= 1


async def test_bench_run_order_is_fixed_by_the_seed(
    lab: LabPort, plan: Callable[..., Plan], now: dt.datetime, tmp_path: Path
) -> None:
    runner = AssessBench(lab, path=PATH, limit=10, temp=tmp_path)
    first, again = [await runner.run(plan(n=4, seed=11), skip=False, now=now) for _ in range(2)]
    assert [s.at for s in first.arms[0].samples] == [s.at for s in again.arms[0].samples]


async def test_bench_run_seconds_is_measured_by_taxis(
    lab: LabPort, plan: Callable[..., Plan], arm: Callable[..., Arm], now: dt.datetime, tmp_path: Path
) -> None:
    timed = arm("fast", Role.CANDIDATE, run=("sleep 0.05", """echo '{"metric": 99, "x": 2}'"""))
    arms = (timed, arm("slow", Role.EMPTY, run=("echo not json",)))
    found = await AssessBench(lab, path=PATH, limit=10, temp=tmp_path).run(
        plan(*arms, metric="seconds", n=1), skip=False, now=now
    )
    sample, plain = found.arms[0].samples[0], found.arms[1].samples[0]
    assert 0.05 <= (sample.metric or 0) < 5
    assert (sample.secondary, plain.error, plain.metric is not None) == ({"x": 2.0}, "", True)


@pytest.mark.parametrize(
    ("script", "error"),
    [
        ("echo oops >&2; exit 4", "exit 4: oops"),
        ("echo hello", "the last stdout line is not JSON: 'hello'"),
        ("echo true", "the last stdout line is not a number: 'true'"),
        ("""echo '{"metric": true}'""", "the metric is not a number: '{\"metric\": true}'"),
        ("""echo '{"other": 1}'""", "the last stdout line is no metric: '{\"other\": 1}'"),
        ("sleep 5", "timed out after 0.3s"),
    ],
    ids=["exit", "prose", "bool", "bool-metric", "no-metric", "timeout"],
)
async def test_bench_run_keeps_a_failed_run(
    lab: LabPort,
    plan: Callable[..., Plan],
    arm: Callable[..., Arm],
    now: dt.datetime,
    tmp_path: Path,
    script: str,
    error: str,
) -> None:
    arms = (arm("fast", Role.CANDIDATE, run=(script,)), arm("slow", Role.INCUMBENT))
    found = await AssessBench(lab, path=PATH, limit=0.3, temp=tmp_path).run(plan(*arms, n=1), skip=False, now=now)
    failed = found.arms[0].samples[0]
    assert (failed.metric, failed.error) == (None, error)


async def test_bench_run_records_a_failed_install_and_sandboxes_each_arm(
    lab: LabPort, plan: Callable[..., Plan], arm: Callable[..., Arm], now: dt.datetime, tmp_path: Path
) -> None:
    arms = (
        arm(
            "fast", Role.CANDIDATE, install=("touch $HOME/marker",), run=("""test -f $HOME/marker && echo ${#CASE}""",)
        ),
        arm("slow", Role.INCUMBENT, install=("echo broken >&2", "exit 7"), run=("echo 1",)),
    )
    found = await AssessBench(lab, path=PATH, limit=10, temp=tmp_path).run(
        plan(*arms, cases=("abc",), n=1), skip=False, now=now
    )
    fast, slow = found.arms
    assert (fast.installed, fast.samples[0].metric) == (True, 3.0)
    assert (slow.installed, slow.error, slow.samples) == (False, "exit 7: broken", ())


@pytest.mark.parametrize(
    ("skip", "knobs", "reason"),
    [
        (True, {"overlap": Overlap.REPLACES}, "bench=false: judged on desk evidence"),
        (False, {"overlap": Overlap.NONE}, "overlap none: nothing to weigh it against"),
        (False, {"arms": ()}, "the plan has no arms: desk only"),
    ],
    ids=["bench-false", "overlap-none", "no-arms"],
)
async def test_bench_run_installs_nothing(
    lab: LabPort, plan: Callable[..., Plan], now: dt.datetime, skip: bool, knobs: dict, reason: str
) -> None:
    found = await AssessBench(lab, path=PATH, limit=10).run(plan(**knobs), skip=skip, now=now)
    assert (found.arms, found.reason, found.machine) == ((), reason, None)


async def test_bench_run_refuses_a_fence_that_does_not_hold(
    leaky_lab: LabPort, plan: Callable[..., Plan], now: dt.datetime, tmp_path: Path
) -> None:
    with pytest.raises(AssessError, match="does not hold"):
        await AssessBench(leaky_lab, path=PATH, limit=10, temp=tmp_path).run(plan(), skip=False, now=now)


async def test_bench_machine_without_cpuinfo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "CPUINFO", str(tmp_path / "absent"))
    machine = await AssessBench._run_machine()
    assert machine.cpu
    assert machine.ram > 0
