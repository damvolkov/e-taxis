"""tests/unit/e_taxis/workflow/distill/report: verdicts, reviews and handoffs joined; the apply commands quoted.

Defect 4 (report side): the `apply:` commands spliced ids and paths into a shell line. Every value is now quoted and
a proposal's text is read from its brief file at run time: a hostile id, path or brief arrives as itself — the
quoting test runs the command in a real bash against a stand-in `taxis` that prints its argv."""

from typing import TYPE_CHECKING

import anyio
import msgspec
import pytest

from e_taxis.workflow.distill.report import DistillReport
from e_taxis.workflow.models.distill import (
    BlueprintArea,
    BlueprintChange,
    BlueprintTarget,
    Change,
    Direction,
    Emaintenance,
    Enhance,
    Fact,
    FactStatus,
    Grade,
    HarnessKind,
    HarnessTarget,
    Judgement,
    Plane,
    Review,
    RunMeta,
    Verdict,
    Waiver,
)
from e_taxis.workflow.models.entity import Entity

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.distill import Candidate

META = RunMeta(
    id="r1", project="/w/e-voice", branches=("feat/x",), base="abc", folder="/runs/r1", work="made it\nfaster"
)


@pytest.fixture
def reporter() -> DistillReport:
    return DistillReport(blueprint="/w/e-arkhetypo", nous="/w/e nous")


async def test_report_joins_verdicts_reviews_and_handoffs(
    reporter: DistillReport, candidate: Callable[..., Candidate], skill_ref
) -> None:
    candidates = (
        candidate("c1", skill_ref, facts=("f1",)),
        candidate(
            "c2",
            BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", layer="src"),
            BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", layer="tests"),
        ),
        candidate("c3", skill_ref),
        candidate("c4", skill_ref),
        candidate("c5", HarnessTarget(kind=HarnessKind.STACK)),
        candidate("c6", skill_ref),
        candidate(
            "c7",
            BlueprintTarget(area=BlueprintArea.STACK, unit="llm/vllm", new=True, path="stack/llm/vllm/compose.yml"),
        ),
    )
    grades = (
        *(Grade(candidate=c.id, matrix="deepening") for c in candidates if c.id != "c6"),
        Grade(candidate="c6", stop=("past its miner's cap",)),
    )
    judgements = (
        Judgement(candidate="c1", verdict=Verdict.MUST, generality=0.9, rationale="lies today"),
        Judgement(candidate="c2", verdict=Verdict.SHOULD, generality=0.6, rationale="better api"),
        Judgement(candidate="c3", verdict=Verdict.SHOULD, generality=0.4, rationale="maybe"),
        Judgement(candidate="c4", verdict=Verdict.CASE, generality=0.1, rationale="only here"),
        Judgement(candidate="c5", verdict=Verdict.SHOULD, generality=0.5, rationale="the stack"),
        Judgement(candidate="c6", verdict=Verdict.MUST, generality=0.9, rationale="judged anyway"),
        Judgement(candidate="c7", verdict=Verdict.SHOULD, generality=0.3, rationale="a service"),
        Judgement(candidate="ghost", verdict=Verdict.MUST, generality=1.0, rationale="never graded"),
    )
    reviews = (
        Review(candidate="c1", upheld=True),
        Review(candidate="c3", upheld=False, objection="already in lib.md", final=Verdict.REJECT),
    )
    facts = (
        Fact(id="f1", plane=Plane.LIBRARY, subject="psqlpy", status=FactStatus.ABSENT),
        Fact(id="f2", plane=Plane.MODULE, subject="ops/decode.py", status=FactStatus.ABSENT),
        Fact(id="f3", plane=Plane.MODULE, subject="ops/url.py", status=FactStatus.ABSENT),
    )
    waivers = (Waiver(fact="f3", reason="shaped for this harvest"), Waiver(fact="f1", reason="answered anyway"))
    stale = (
        Fact(
            id="module:ops/a.py",
            plane=Plane.MODULE,
            subject="ops/a.py",
            status=FactStatus.DIVERGED,
            direction=Direction.BEHIND,
            detail="template +2 -1",
        ),
    )
    built = reporter.build(
        META,
        candidates=candidates,
        grades=grades,
        judgements=judgements,
        reviews=reviews,
        facts=facts,
        waivers=waivers,
        stale=stale,
    )
    cover = {c.plane: c for c in built.coverage}
    assert [(p.candidate.id, p.judgement.verdict) for p in built.proposals] == [
        ("c1", Verdict.MUST),
        ("c2", Verdict.SHOULD),
        ("c5", Verdict.SHOULD),
        ("c7", Verdict.SHOULD),
    ]
    assert [type(p.handoff) for p in built.proposals] == [Emaintenance, BlueprintChange, Enhance, BlueprintChange]
    assert (cover[Plane.LIBRARY].facts, cover[Plane.LIBRARY].open) == (1, ())
    assert [f.id for f in cover[Plane.MODULE].open] == ["f2"]
    assert [(f.id, why) for f, why in cover[Plane.MODULE].waived] == [("f3", "shaped for this harvest")]
    assert [j.candidate for j in built.cases] == ["c4"]
    assert [(j.candidate, j.rationale) for j in built.rejected] == [
        ("c3", "already in lib.md"),
        ("c6", "stopped: past its miner's cap"),
    ]
    text = reporter.render(built)
    body, annex = text.split("\n---\n", 1)
    assert "| skills | algo-py-core | **must** | sketch c1 | [c1](#c1) |" in body
    assert "| projects | api (src, tests) | **should** | sketch c2 | [c2](#c2) |" in body
    assert "| `module:ops/a.py` | behind: template +2 -1 |" in body
    assert "> made it faster" in body
    assert "### c1" in annex
    assert "taxis workflow run emaintenance --nous '/w/e nous' entity=skill op=update id=algo-py-core" in annex
    assert "f3: shaped for this harvest" in annex
    assert reporter.briefs(built)["/runs/r1/briefs/c1.md"].startswith("sketch c1")


async def test_report_renders_an_empty_run(reporter: DistillReport) -> None:
    built = reporter.build(
        RunMeta(id="r", project="/p", branches=("b",), base="abc"), candidates=(), grades=(), judgements=(), reviews=()
    )
    text = reporter.render(built)
    assert text.count("Nothing proposed here.") == 2
    assert "Annex A — harness proposals\n\nNone." in text
    assert (
        "## The project's own drift\n\nBehind its blueprint: to fix in the project, nothing to learn.\n\nNone." in text
    )


async def test_report_long_title_is_cut_on_a_word(
    reporter: DistillReport, candidate: Callable[..., Candidate], skill_ref
) -> None:
    long = msgspec.structs.replace(candidate("c1", skill_ref), sketch=" ".join(["word"] * 40))
    assert reporter._render_title(long).endswith("word…")


@pytest.mark.parametrize(
    "hostile",
    ["it's", 'say "hi"', "$(touch {canary})", "`touch {canary}`", "a; touch {canary}", "two\nlines"],
    ids=["squote", "dquote", "subshell", "backtick", "semicolon", "newline"],
)
async def test_report_apply_command_carries_every_value_as_itself(
    reporter: DistillReport, tmp_path: Path, hostile: str
) -> None:
    canary = tmp_path / "pwned"
    value = hostile.replace("{canary}", str(canary))
    folder = tmp_path / f"run {value}"
    brief = folder / "briefs" / "c1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text(f"the brief: {value}")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "taxis").write_text("#!/bin/sh\nprintf '%s\\0' \"$@\"\n")
    (bin_dir / "taxis").chmod(0o755)
    handoff = Emaintenance(entity=Entity.SKILL, op=Change.UPDATE, id=value, details="unused")
    line = DistillReport(blueprint="/b", nous=value).command(handoff, str(brief))
    done = await anyio.run_process(["bash", "-c", line], env={"PATH": f"{bin_dir}:/usr/bin:/bin"})
    argv = done.stdout.decode().split("\0")[:-1]
    assert argv == [
        "workflow",
        "run",
        "emaintenance",
        "--nous",
        value,
        "entity=skill",
        "op=update",
        f"id={value}",
        f"details=the brief: {value}",
    ]
    assert not canary.exists()


async def test_report_ship_runs_only_the_musts_of_a_workflow(
    reporter: DistillReport, candidate: Callable[..., Candidate], skill_ref
) -> None:
    candidates = (
        candidate("c1", skill_ref),
        candidate("c2", skill_ref),
        candidate("c3", BlueprintTarget(area=BlueprintArea.INFRA, unit="jobs")),
    )
    built = reporter.build(
        META,
        candidates=candidates,
        grades=tuple(Grade(candidate=c.id) for c in candidates),
        judgements=(
            Judgement(candidate="c1", verdict=Verdict.MUST, generality=0.9, rationale="r"),
            Judgement(candidate="c2", verdict=Verdict.SHOULD, generality=0.9, rationale="r"),
            Judgement(candidate="c3", verdict=Verdict.MUST, generality=0.9, rationale="r"),
        ),
        reviews=(),
    )
    assert reporter.ship(built) == (
        (
            "taxis workflow run emaintenance --nous '/w/e nous' entity=skill op=update id=algo-py-core "
            'details="$(cat /runs/r1/briefs/c1.md)"'
        ),
    )
    by = {p.candidate.id: p for p in built.proposals}
    assert reporter.command(by["c3"].handoff, "x") == "git -C /w/e-arkhetypo switch -c distill/r1-c3"
