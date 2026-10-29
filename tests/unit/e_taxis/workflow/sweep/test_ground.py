"""tests/unit/e_taxis/workflow/sweep/ground: merged, re-fetched, kept only where a fetched page holds a fact, ranked."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.sweep import Findings
from e_taxis.workflow.sweep.ground import SweepGround

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.sweep import Finding

REPO = "https://github.com/spanline/spanline"
VOICES = frozenset({"ada"})


async def test_ground_keeps_what_a_page_holds(web, finding: Callable[..., Finding]) -> None:
    kept = finding(
        "Spanline", facts=("an   OPENTELEMETRY exporter", "invented claim"), links=(REPO, "https://gone.example")
    )
    grounded = await SweepGround(web).ground((Findings(findings=(kept,)),), VOICES)
    (only,) = grounded.findings
    assert (only.links, only.facts) == ((REPO,), ("an   OPENTELEMETRY exporter",))


async def test_ground_drops_and_says_why(web, finding: Callable[..., Finding]) -> None:
    dead = finding("Dead", links=("https://gone.example",))
    loose = finding("Loose", facts=("nowhere on the page",))
    grounded = await SweepGround(web).ground((Findings(findings=(dead, loose)),), VOICES)
    assert grounded.findings == ()
    assert grounded.notes == "ground: 0 of 2 kept · Dead: no link answered · Loose: no fact on its pages"


async def test_ground_merges_the_same_system(web, finding: Callable[..., Finding]) -> None:
    voice = finding(
        "Spanline", relevance=3, via="ada", sources=("https://www.linkedin.com/posts/a",), published_at="2026-10-27"
    )
    search = finding(
        "spanline ", relevance=4, sources=("https://news.example/s",), entities=("OTel",), published_at="2026-10-25"
    )
    linked = finding("Spanline SDK", relevance=2, via="ada", links=(REPO + "/",), sources=("https://x.example",))
    other = finding("Other", relevance=4, via="search", facts=("Docs",), links=(REPO + "/docs",))
    web.pages[REPO + "/"] = web.pages[REPO + "/docs"] = web.pages[REPO]
    grounded = await SweepGround(web).ground(
        (Findings(findings=(voice, linked)), Findings(findings=(search, other))), VOICES
    )
    merged, rest = grounded.findings
    assert (merged.title, merged.relevance, merged.via, merged.published_at) == ("spanline ", 4, "ada", "2026-10-25")
    assert merged.sources == ("https://news.example/s", "https://www.linkedin.com/posts/a", "https://x.example")
    assert (merged.links, merged.entities) == ((REPO, REPO + "/"), ("OTel",))
    assert rest.title == "Other"


async def test_ground_ranks_relevance_then_vouching(web, finding: Callable[..., Finding]) -> None:
    web.pages[REPO + "/a"] = web.pages[REPO + "/b"] = web.pages[REPO]
    found = (
        finding("A", relevance=3, via="search", links=(REPO + "/a",)),
        finding("B", relevance=5, via="search", links=(REPO + "/b",)),
        finding("C", relevance=3, via="ada"),
    )
    grounded = await SweepGround(web).ground((Findings(findings=found),), VOICES)
    assert [f.title for f in grounded.findings] == ["B", "C", "A"]
    assert grounded.notes == "ground: 3 of 3 kept"
