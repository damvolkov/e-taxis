"""tests/unit/e_taxis/workflow/sweep/fetch: every voice read with its kind's parser, its window kept, its pages fetched;
a voice that fails is a row with its error, never a missing one."""

import pytest

from e_taxis.workflow.models.sweep import Frame, Seen, Voice, VoiceKind, VoiceStatus
from e_taxis.workflow.sweep.fetch import SweepFetch

FEED = Voice(id="blog", url="https://blog.example/feed/", kind=VoiceKind.ATOM_FEED)
ADA = Voice(id="ada", url="https://www.linkedin.com/in/adavoice", kind=VoiceKind.LINKEDIN_PROFILE)
DOWN = Voice(id="down", url="https://down.example/feed", kind=VoiceKind.ATOM_FEED)
SITE = Voice(id="site", url="https://github.com/spanline/spanline", kind=VoiceKind.WEB)
POST = "https://www.linkedin.com/posts/adavoice_tracing-otel-activity-1111111111111111111-AbCd"
ARTICLE = "https://www.linkedin.com/pulse/traces-are-contract-ada-ledger-abcde"


def frame(since: str, until: str, *voices: Voice) -> Frame:
    return Frame(brief="b", topic="", keywords=(), since=since, until=until, voices=voices)


async def test_fetch_reads_every_voice(web) -> None:
    seen = Seen(seen={"ada": {POST: "2026-10-27"}})
    entries = await SweepFetch(web).fetch(frame("2026-10-26", "2026-10-28", FEED, ADA, DOWN, SITE), seen)
    rows = [(v.id, v.status, v.parsed, v.in_window, v.new) for v in entries.voices]
    assert rows == [
        ("blog", VoiceStatus.EMPTY, 3, 0, 0),
        ("ada", VoiceStatus.OK, 3, 2, 1),
        ("down", VoiceStatus.ERROR, 0, 0, 0),
        ("site", VoiceStatus.OK, 1, 1, 1),
    ]
    assert entries.voices[2].error == "https://down.example/feed: 404 Not Found"
    article, post = entries.voices[1].entries
    assert (article.url, article.teaser, article.new) == (ARTICLE, True, True)
    assert (post.url, post.teaser, post.new) == (POST, False, False)
    assert post.links == ("https://github.com/spanline/spanline",)


async def test_fetch_feed_reads_the_entry_page(web) -> None:
    (voice,) = (await SweepFetch(web).fetch(frame("2026-04-29", "2026-04-30", FEED), Seen())).voices
    (entry,) = voice.entries
    assert (voice.parsed, voice.in_window, voice.new) == (3, 1, 1)
    assert (entry.title, entry.teaser) == ("Sequoia Ascent 2026 summary", False)
    assert entry.text.startswith("Spanline Spanline is")


@pytest.mark.parametrize(
    ("published", "inside"),
    [
        ("2026-10-25T23:30:00Z", True),
        ("2026-10-25T22:30:00Z", False),
        ("2026-10-28T22:59:00Z", True),
        ("2026-10-28T23:00:00Z", False),
        ("2026-10-27T10:00:00", True),
        ("", True),
        ("last tuesday", True),
    ],
    ids=["madrid-since", "before", "madrid-until", "after", "naive-utc", "undated", "unreadable"],
)
async def test_fetch_window_is_madrid_calendar_days(web, published: str, inside: bool) -> None:
    web.pages[SITE.url] = f'<meta property="article:published_time" content="{published}"><p>x</p>'
    (voice,) = (await SweepFetch(web).fetch(frame("2026-10-26", "2026-10-28", SITE), Seen())).voices
    assert voice.in_window == int(inside)
