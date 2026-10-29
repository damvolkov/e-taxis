"""tests/unit/e_taxis/workflow/commands/compare: `taxis workflow radar-stack <step>` through the real app, step after
step — the agents' answers read from the steps the workflow's ports name (`hunt`, `plan-it`, `judge`, `attack` here)."""

from typing import TYPE_CHECKING, Any

import msgspec

from e_taxis.workflow.models.assess import Registry
from e_taxis.workflow.models.compare import (
    Challenge,
    Compared,
    Decision,
    Destination,
    Migration,
    Plans,
    Report,
    Reviews,
    Rivalry,
    Rivals,
    Ruling,
    Shortlist,
    Stack,
    Subject,
    Verdicts,
    Weighed,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.assess import Plan

type Taxis = Callable[..., tuple[int, str, str]]
STEP = ("workflow", "radar-stack")
MSGSPEC = Subject(name="msgspec", repo="msgspec/msgspec", package="msgspec", registry=Registry.PYPI)
BARE = Subject(name="homegrown")


def read(rundir: Path, name: str, kind: Any) -> Any:
    return msgspec.json.decode((rundir / "radar" / f"{name}.json").read_bytes(), type=kind)


def test_compare_steps_end_to_end(
    taxis: Taxis,
    assess_world: Path,
    nous: Path,
    rundir: Path,
    resources,
    answer: Callable[[str, Any], None],
    plan: Callable[..., Plan],
) -> None:
    run, at = ("--rundir", str(rundir)), ("--nous", str(nous))
    project = resources.path / "compare" / "project"
    assert taxis(*STEP, "intake", *run, *at, "--project", str(project), "--query", "better?")[0] == 0
    assert read(rundir, "stack", Stack).query == "better?"
    answer("hunt", Rivals(incumbents=(Rivalry(incumbent=BARE, role="ser", rivals=(MSGSPEC,)),)))
    assert taxis(*STEP, "health", *run, *at)[0] == 0
    code, out, _ = taxis(*STEP, "rank", *run, *at)
    assert (code, "1 of 1 incumbents earn a bench" in out) == (0, True)
    assert read(rundir, "shortlist", Shortlist).contests[0].rival == "msgspec"
    weighed = Weighed(
        incumbent="homegrown", rival="msgspec", plan=plan(), migration=Migration(files=("a.py",), changes=())
    )
    answer("plan-it", Plans(pairs=(weighed,)))
    assert taxis(*STEP, "bench", *run, *at, "--bench", "false")[0] == 0
    assert taxis(*STEP, "stats", *run, *at)[0] == 0
    ruling = Ruling(
        incumbent="homegrown",
        rival="msgspec",
        decision=Decision.TRIAL,
        evidence=("x",),
        landing=Destination.PROJECT,
        command="git switch -c msgspec",
    )
    answer("judge", Verdicts(verdicts=(ruling,)))
    answer(
        "attack",
        Reviews(reviews=(Challenge(incumbent="homegrown", stands=True, objections=(), decision=Decision.TRIAL),)),
    )
    code, out, _ = taxis(*STEP, "report", *run, *at)
    assert (code, "homegrown — trial" in out) == (0, True)
    assert read(rundir, "compare", Report).settled[0].decision is Decision.TRIAL
    index = msgspec.json.decode((assess_world / "compared.json").read_bytes(), type=dict[str, Compared])
    assert index["homegrown"].verdict is Decision.TRIAL


def test_compare_rank_that_keeps_everything_reports_and_exits_3(
    taxis: Taxis, assess_world: Path, nous: Path, rundir: Path, resources, answer: Callable[[str, Any], None]
) -> None:
    run, at = ("--rundir", str(rundir)), ("--nous", str(nous))
    project = resources.path / "compare" / "project"
    taxis(*STEP, "intake", *run, *at, "--project", str(project), "--query", "better?")
    answer("hunt", Rivals(incumbents=(Rivalry(incumbent=MSGSPEC, role="ser", rivals=(BARE,)),)))
    taxis(*STEP, "health", *run, *at)
    code, out, _ = taxis(*STEP, "rank", *run, *at)
    assert (code, "msgspec — keep" in out) == (3, True)
    assert (rundir / "radar" / "report.md").is_file()


def test_compare_schemas_write_then_check(taxis: Taxis, nous: Path) -> None:
    folder = nous / "core" / "tekton" / "workflows" / "radar-stack" / "schemas"
    (folder / "Stack.json").write_text("{}")
    code, _, err = taxis(*STEP, "schemas", "--nous", str(nous), "--check")
    assert (code, "stale schemas" in err, "Stack" in err) == (35, True, True)
    assert taxis(*STEP, "schemas", "--nous", str(nous))[0] == 0
    code, out, _ = taxis(*STEP, "schemas", "--nous", str(nous), "--check")
    assert (code, "10 in sync" in out) == (0, True)
