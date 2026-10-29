"""tests/unit/e_taxis/workflow/sweep/report: the sweep as written — per voice, the findings ranked, the assess commands,
and what the ledger records."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.sweep import (
    Entries,
    Entry,
    Findings,
    FindingStatus,
    Frame,
    Voice,
    VoiceEntries,
    VoiceKind,
    VoiceStatus,
)
from e_taxis.workflow.sweep.report import SweepReport

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.sweep import Finding

FRAME = Frame(
    brief="Agentic systems, watched.",
    topic="observability",
    keywords=("agent tracing",),
    since="2026-10-26",
    until="2026-10-28",
    voices=(Voice(id="ada", url="https://www.linkedin.com/in/adavoice", kind=VoiceKind.LINKEDIN_PROFILE),),
)
ENTRIES = Entries(
    voices=(
        VoiceEntries(
            id="ada",
            status=VoiceStatus.OK,
            parsed=3,
            in_window=1,
            new=1,
            entries=(Entry(url="https://www.linkedin.com/posts/a", published_at="2026-10-27", text="t"),),
        ),
        VoiceEntries(id="down", status=VoiceStatus.ERROR, error="https://down: 404 Not Found"),
    )
)


@pytest.fixture
def fitted(finding: Callable[..., Finding]) -> Findings:
    """A new finding worth assessing (a URL a shell must not split), a known one, and a new one worth less."""
    return Findings(
        findings=(
            finding(
                "Spanline", relevance=5, via="ada", status=FindingStatus.NEW, links=("https://g.example/s?a=1&b=2",)
            ),
            finding("Langfuse", relevance=4, status=FindingStatus.HAVE, incumbent="langfuse — lib.md"),
            finding("Minor", relevance=3, status=FindingStatus.NEW, entities=("X",)),
        ),
        notes="ground: 3 of 4 kept · Dead: no link answered",
    )


async def test_report_build_counts_and_assesses(fitted: Findings) -> None:
    built = SweepReport().build(ENTRIES, fitted, "/run/report.md")
    assert built.path == "/run/report.md"
    assert [(row.id, row.status, row.findings) for row in built.voices] == [
        ("ada", VoiceStatus.OK, 1),
        ("down", VoiceStatus.ERROR, 0),
    ]
    assert built.assess == ("taxis workflow run soa-assess 'tech=https://g.example/s?a=1&b=2'",)
    assert [f.title for f in built.findings] == ["Spanline", "Langfuse", "Minor"]


async def test_report_render_reads_as_the_sweep(fitted: Findings) -> None:
    text = SweepReport().render(FRAME, SweepReport().build(ENTRIES, fitted, "/run/report.md"), fitted.notes)
    assert text.startswith("# soa-sweep — observability · 2026-10-26 → 2026-10-28\n\nAgentic systems, watched.\n")
    assert "| ada | ok | 3 · 1 · 1 | 1 |" in text
    assert "| down | error: https://down: 404 Not Found | 0 · 0 · 0 | 0 |" in text
    assert "### 1. Spanline — tool · 5/5 · new" in text
    assert "`taxis workflow run soa-assess 'tech=https://g.example/s?a=1&b=2'`" in text
    assert "Incumbent: langfuse — lib.md" in text
    assert "Entities: X" in text
    assert text.endswith("ground: 3 of 4 kept · Dead: no link answered\n")


async def test_report_render_of_an_empty_plane() -> None:
    plane = Frame(brief="b", topic="", keywords=(), since="2026-10-26", until="2026-10-28", voices=())
    built = SweepReport().build(Entries(voices=()), Findings(findings=()), "/r")
    text = SweepReport().render(plane, built, "")
    assert text.startswith("# soa-sweep — the whole plane · 2026-10-26 → 2026-10-28")
    assert "Nothing survived grounding." in text


async def test_report_seen_records_entries_and_finding_links(fitted: Findings) -> None:
    built = SweepReport().build(ENTRIES, fitted, "/r")
    assert SweepReport().seen(FRAME, ENTRIES, built) == {
        "ada": {"https://www.linkedin.com/posts/a": "2026-10-28", "https://g.example/s?a=1&b=2": "2026-10-28"},
        "search": {"https://github.com/spanline/spanline": "2026-10-28"},
    }
