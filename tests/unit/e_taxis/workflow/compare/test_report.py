"""tests/unit/e_taxis/workflow/compare/report: per incumbent, what stood — kept by the rubric, the ruling the adversary
let stand, or the reviewer's own when it sank it — rendered and indexed."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.workflow.compare.report import CompareReport
from e_taxis.workflow.models.assess import Objection, Outcome, Stats
from e_taxis.workflow.models.compare import (
    Challenge,
    Compared,
    Contest,
    Decision,
    Dependency,
    Destination,
    Ecosystem,
    Measured,
    Migration,
    PairStats,
    Plans,
    Reviews,
    Ruling,
    Score,
    Shortlist,
    Stack,
    Verdicts,
    Weighed,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.assess import Plan

STACK = Stack(
    project="/repo",
    query="better?",
    manifests=("pyproject.toml",),
    dependencies=(Dependency(name="msgspec", ecosystem=Ecosystem.PYTHON, manifest="pyproject.toml"),),
)
SCORES = (Score(name="msgspec", total=0.5, terms={"rust": 0.25}, stars=3), Score(name="orjson", total=0.7, terms={}))
SHORTLIST = Shortlist(
    weights={},
    margin=0.05,
    contests=(
        Contest(incumbent="msgspec", role="ser", scores=SCORES, reason="orjson scores 0.7", rival="orjson"),
        Contest(incumbent="wreq", role="http", scores=(), reason="kept by the rubric: no rival named"),
    ),
)
RULING = Ruling(
    incumbent="msgspec",
    rival="orjson",
    decision=Decision.REPLACE,
    evidence=("faster",),
    landing=Destination.NOUS,
    command="taxis enhance run skill lang-py-datamodel",
)


@pytest.mark.parametrize(
    ("stands", "decision", "line"),
    [(True, Decision.REPLACE, "the adversary let it stand"), (False, Decision.KEEP, "the adversary sank replace")],
    ids=["stands", "sunk"],
)
async def test_report_settles_each_incumbent(
    plan: Callable[..., Plan], tmp_path: Path, stands: bool, decision: Decision, line: str
) -> None:
    plans = Plans(
        pairs=(
            Weighed(
                incumbent="msgspec",
                rival="orjson",
                plan=plan(),
                migration=Migration(files=("a.py",), changes=("swap",)),
            ),
        )
    )
    stats = PairStats(
        pairs=(
            Measured(
                incumbent="msgspec", rival="orjson", stats=Stats(metric="ms", outcome=Outcome.BETTER, low=1.0, high=2.0)
            ),
        )
    )
    review = Challenge(
        incumbent="msgspec",
        stands=stands,
        objections=(Objection(claim="slow", refuted=stands),),
        decision=Decision.KEEP,
    )
    reporter = CompareReport()
    built = reporter.build(
        STACK,
        SHORTLIST,
        (plans, stats, Verdicts(verdicts=(RULING,)), Reviews(reviews=(review,))),
        date="2026-10-29",
        path="/r.md",
    )
    first, second = built.settled
    assert (first.decision, first.proposed, first.declared[0].name, first.migration and first.migration.files) == (
        decision,
        Decision.REPLACE,
        "msgspec",
        ("a.py",),
    )
    assert (second.decision, second.reason) == (Decision.KEEP, "kept by the rubric: no rival named")
    text = reporter.render(built)
    assert line in text
    assert "bench: better [1.0, 2.0]" in text
    assert "- file: a.py" in text
    index = await reporter.record(tmp_path, built)
    assert msgspec.json.decode(index.read_bytes(), type=dict[str, Compared])["wreq"].verdict is Decision.KEEP


async def test_report_without_rulings_keeps_everything(tmp_path: Path) -> None:
    empty = (Plans(pairs=()), PairStats(pairs=()), Verdicts(verdicts=()), Reviews(reviews=()))
    reporter = CompareReport()
    built = reporter.build(STACK, SHORTLIST, empty, date="2026-10-29", path="/r.md")
    assert [item.decision for item in built.settled] == [Decision.KEEP, Decision.KEEP]
    (tmp_path / "compared.json").write_bytes(
        msgspec.json.encode({"old": Compared(verdict=Decision.TRIAL, date="d", report="r")})
    )
    index = await reporter.record(tmp_path, built)
    assert set(msgspec.json.decode(index.read_bytes())) == {"old", "msgspec", "wreq"}
    assert "not benched" in reporter.render(built)
