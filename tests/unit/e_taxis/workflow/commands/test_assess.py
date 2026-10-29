"""tests/unit/e_taxis/workflow/commands/assess: `taxis workflow radar-tech <step>` through the real app, step after step
— the agents' answers read from the steps the workflow's ports name (`weigh-it`, `judge`, `attack` here)."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.assess import (
    Arm,
    Cache,
    Candidate,
    Health,
    Inventory,
    Landing,
    Outcome,
    Overlap,
    Plan,
    Report,
    Review,
    Ring,
    Role,
    Samples,
    Stats,
    Verdict,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

type Taxis = Callable[..., tuple[int, str, str]]
STEP = ("workflow", "radar-tech")
PLAN = Plan(
    incumbent="slow",
    overlap=Overlap.REPLACES,
    hypothesis="fast answers in fewer ms",
    metric="ms",
    threshold=0.5,
    higher_is_better=False,
    cases=("a", "b"),
    n=3,
    cache=Cache.WARM,
    arms=(
        Arm(name="fast", role=Role.CANDIDATE, install=("true",), run=("echo 1",)),
        Arm(name="slow", role=Role.INCUMBENT, install=(), run=("echo 2",)),
    ),
    landing="a lib.md row",
)


def read(rundir: Path, name: str, kind: Any) -> Any:
    return msgspec.json.decode((rundir / "radar" / f"{name}.json").read_bytes(), type=kind)


def test_assess_steps_end_to_end(
    taxis: Taxis, assess_world: Path, nous: Path, rundir: Path, answer: Callable[[str, Any], None]
) -> None:
    run, at = ("--rundir", str(rundir)), ("--nous", str(nous))
    code, out, _ = taxis(*STEP, "intake", *at, *run, "--tech", "https://github.com/rtk-ai/rtk", "--topic", "memory")
    assert (code, read(rundir, "candidate", Candidate).topic) == (0, "memory")
    assert "note: crates 'rtk' points at reachingforthejack/rtk" in out
    code, out, _ = taxis(*STEP, "inventory", *at, *run)
    assert (code, read(rundir, "inventory", Inventory).assessed) == (0, ())
    assert "rows in the domain · 0 past assessments" in out
    code, out, _ = taxis(*STEP, "health", *run)
    assert (code, read(rundir, "health", Health).contributors) == (0, 192)
    assert "5/8 KPIs · 1 failed" in out
    answer("weigh-it", PLAN)
    code, out, _ = taxis(*STEP, "bench", *at, *run, "--bench", "")
    assert (code, "2/2 arms installed · 12 samples kept" in out) == (0, True)
    assert [len(arm.samples) for arm in read(rundir, "samples", Samples).arms] == [6, 6]
    code, out, _ = taxis(*STEP, "stats", *at, *run)
    stats = read(rundir, "stats", Stats)
    assert (code, stats.outcome, stats.mean, stats.pairs) == (0, Outcome.BETTER, -1.0, 6)
    assert "ms: better [-1, -1]" in out
    answer(
        "judge",
        Verdict(verdict=Ring.ADOPT, evidence=("1 ms less",), landing=Landing.NOUS, command="taxis enhance run skill x"),
    )
    answer("attack", Review(stands=True, objections=(), verdict=Ring.ADOPT))
    code, out, _ = taxis(*STEP, "report", *at, *run)
    assert (code, read(rundir, "assess", Report).verdict) == (0, Ring.ADOPT)
    assert not (rundir / "report.md").exists()
    assert (rundir / "radar" / "report.md").read_text().startswith("# radar-tech · rtk — adopt")
    assert f"indexed: {assess_world / 'assessed.json'}" in out
    assert msgspec.json.decode((assess_world / "assessed.json").read_bytes())["rtk"]["verdict"] == "adopt"


@pytest.mark.parametrize(("flag", "reason"), [("false", "bench=false"), ("", "overlap none")], ids=["flag", "overlap"])
def test_assess_bench_installs_nothing(
    taxis: Taxis,
    assess_world: Path,
    nous: Path,
    rundir: Path,
    answer: Callable[[str, Any], None],
    flag: str,
    reason: str,
) -> None:
    answer("weigh-it", msgspec.structs.replace(PLAN, overlap=Overlap.NONE if not flag else Overlap.REPLACES))
    code, out, _ = taxis(*STEP, "bench", "--nous", str(nous), "--rundir", str(rundir), "--bench", flag)
    assert (code, reason in out, read(rundir, "samples", Samples).arms) == (0, True, ())
    code, out, _ = taxis(*STEP, "stats", "--nous", str(nous), "--rundir", str(rundir))
    assert (code, read(rundir, "stats", Stats).outcome) == (0, Outcome.UNMEASURED)
    assert f"ms: not measured — {reason}" in out


@pytest.mark.parametrize(
    ("tokens", "err"),
    [
        (("intake", "--nous", "{nous}", "--tech", "https://github.com/nobody/nothing"), "nothing resolvable"),
        (("health",), "no artifact candidate"),
    ],
    ids=["unresolvable", "no-candidate"],
)
def test_assess_step_refuses(
    taxis: Taxis, assess_world: Path, nous: Path, rundir: Path, tokens: tuple[str, ...], err: str
) -> None:
    code, _, said = taxis(*STEP, *(token.format(nous=nous) for token in tokens), "--rundir", str(rundir))
    assert (code, err in said) == (34, True)


def test_assess_bench_refuses_a_misfit_plan(
    taxis: Taxis, assess_world: Path, nous: Path, rundir: Path, answer: Callable[[str, Any], None]
) -> None:
    answer("weigh-it", {"incumbent": "x"})
    code, _, err = taxis(*STEP, "bench", "--nous", str(nous), "--rundir", str(rundir))
    assert (code, "step weigh-it's answer does not fit Plan" in err) == (34, True)


def test_assess_schemas_write_then_check(taxis: Taxis, nous: Path) -> None:
    folder = nous / "core" / "tekton" / "workflows" / "radar-tech" / "schemas"
    (folder / "Plan.json").unlink()
    code, _, err = taxis(*STEP, "schemas", "--nous", str(nous), "--check")
    assert (code, "stale schemas" in err, "Plan" in err) == (34, True, True)
    code, out, _ = taxis(*STEP, "schemas", "--nous", str(nous))
    assert (code, "schemas: 1 written" in out, (folder / "Plan.json").is_file()) == (0, True, True)
    code, out, _ = taxis(*STEP, "schemas", "--nous", str(nous), "--check")
    assert (code, "schemas: 10 in sync" in out) == (0, True)
