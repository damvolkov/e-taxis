"""tests/unit/e_taxis/workflow/assess/report: what stood after the adversary, report.md, and the state's index."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.workflow.assess.report import AssessReport
from e_taxis.workflow.models.assess import (
    Candidate,
    Health,
    Landing,
    Objection,
    Outcome,
    Registry,
    Report,
    Review,
    Ring,
    Stats,
    Verdict,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.assess import Plan

VERDICT = Verdict(
    verdict=Ring.ADOPT,
    evidence=("faster by 2 ms",),
    landing=Landing.NOUS,
    command="taxis enhance run skill x",
    target="x",
)
HEALTH = Health(
    measured_at="2026-10-28T15:00:00+00:00",
    license="MIT",
    contributors=4,
    sources={"license": "https://api.github.com/repos/o/r"},
    failed=("scorecard: gone",),
    notes=("no registry",),
)
MEASURED = Stats(
    metric="ms",
    outcome=Outcome.BETTER,
    candidate="fast",
    baseline="slow",
    pairs=3,
    mean=-2.0,
    low=-2.5,
    high=-1.5,
    threshold=0.5,
    resamples=100,
    confidence=0.95,
    secondary={"runs": "fast 3/3 measured"},
)


@pytest.fixture
def built(plan: Callable[..., Plan], tmp_path: Path) -> Callable[..., Report]:
    def build(review: Review, stats: Stats = MEASURED, candidate: Candidate | None = None) -> Report:
        return AssessReport.build(
            candidate
            or Candidate(
                tech="t", name="r", repo="o/r", package="r", registry=Registry.PYPI, topic="memory", notes=("n1",)
            ),
            plan=plan(),
            health=HEALTH,
            stats=stats,
            verdict=VERDICT,
            review=review,
            path=tmp_path / "report.md",
            date="2026-10-28",
        )

    return build


@pytest.mark.parametrize(
    ("review", "verdict", "said"),
    [
        (
            Review(
                stands=True,
                objections=(Objection(claim="metric chosen late", refuted=True, evidence="plan first"),),
                verdict=Ring.ADOPT,
            ),
            Ring.ADOPT,
            "the adversary let it stand",
        ),
        (
            Review(
                stands=False, objections=(Objection(claim="arm not comparable", refuted=False),), verdict=Ring.TRIAL
            ),
            Ring.TRIAL,
            "the adversary sank the proposed **adopt**",
        ),
    ],
    ids=["stands", "sunk"],
)
async def test_report_build_and_render(
    built: Callable[..., Report], plan: Callable[..., Plan], review: Review, verdict: Ring, said: str
) -> None:
    report = built(review)
    text = AssessReport().render(report, plan())
    assert (report.verdict, report.proposed, report.stands) == (verdict, Ring.ADOPT, review.stands)
    assert text.startswith(
        f"# radar-tech · r — {verdict}\n\n`t` · repo o/r · pypi r · topic memory · 2026-10-28\n\n- n1"
    )
    assert said in text
    assert "`taxis enhance run skill x`" in text
    assert "| license | MIT | https://api.github.com/repos/o/r |" in text
    assert "| scorecard | — | — |" in text
    assert (
        "fast - slow: mean -2, 95% interval [-2.5, -1.5] over 3 pairs (100 paired-bootstrap resamples) → **better**"
        in text
    )


async def test_report_render_unmeasured(built: Callable[..., Report], plan: Callable[..., Plan]) -> None:
    stats = Stats(metric="ms", outcome=Outcome.UNMEASURED, reason="bench=false: judged on desk evidence")
    report = built(Review(stands=True, objections=(), verdict=Ring.HOLD), stats, Candidate(tech="t", name="t"))
    text = AssessReport().render(report, plan())
    assert "**not measured** — bench=false: judged on desk evidence" in text
    assert "`t` · no source · 2026-10-28" in text
    assert "Objections: none" in text


async def test_report_record_keeps_the_latest_per_name(built: Callable[..., Report], tmp_path: Path) -> None:
    state = tmp_path / "state"
    first = built(Review(stands=True, objections=(), verdict=Ring.ADOPT))
    await AssessReport.record(state, msgspec.structs.replace(first, name="other"))
    await AssessReport.record(state, first)
    index = await AssessReport.record(state, msgspec.structs.replace(first, verdict=Ring.HOLD, date="2026-10-29"))
    rows = msgspec.json.decode(index.read_bytes())
    assert rows == {
        "other": {"verdict": "adopt", "date": "2026-10-28", "report": str(tmp_path / "report.md")},
        "r": {"verdict": "hold", "date": "2026-10-29", "report": str(tmp_path / "report.md")},
    }
