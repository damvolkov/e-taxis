"""tests/unit/e_taxis/workflow/sweep/parse: one parser per voice kind — the listing's entries, then each entry's page."""

import pytest

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Entry, Voice, VoiceKind
from e_taxis.workflow.sweep.parse import PARSERS, AtomParse, LinkedinParse, WebParse

FEED = Voice(id="blog", url="https://blog.example/feed/", kind=VoiceKind.ATOM_FEED)
PROFILE = Voice(id="ada", url="https://www.linkedin.com/in/adavoice/", kind=VoiceKind.LINKEDIN_PROFILE)
SITE = Voice(id="site", url="https://spanline.dev/", kind=VoiceKind.WEB)
POST = "https://www.linkedin.com/posts/adavoice_tracing-otel-activity-1111111111111111111-AbCd"


async def test_parse_table_covers_every_kind() -> None:
    assert set(PARSERS) == set(VoiceKind)


async def test_atom_entries_read_the_feed(feed_xml: str) -> None:
    entries = AtomParse().entries(feed_xml, FEED)
    assert [(e.url, e.published_at) for e in entries] == [
        ("https://karpathy.bearblog.dev/sequoia-ascent-2026/", "2026-04-30T16:00:00+00:00"),
        ("https://karpathy.bearblog.dev/year-in-review-2025/", "2025-12-19T18:00:00+00:00"),
        ("https://karpathy.bearblog.dev/finding-the-best-sleep-tracker/", "2025-03-24T23:00:00+00:00"),
    ]
    assert entries[0].title == "Sequoia Ascent 2026 summary"
    assert entries[0].text.startswith("I did a fireside chat at Sequoia Ascent 2026.")
    assert "https://www.youtube.com/watch?v=96jN2OCOfLs" in entries[0].links
    assert entries[0].teaser


@pytest.mark.parametrize(
    ("body", "said"),
    [("<html><body>login</body></html>", "not an Atom feed"), ("<feed", "not an Atom feed")],
    ids=["html", "broken"],
)
async def test_atom_entries_refuse_what_is_no_feed(body: str, said: str) -> None:
    with pytest.raises(SweepError, match=said):
        AtomParse().entries(body, FEED)


async def test_atom_entry_without_content_or_link() -> None:
    feed = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://b/1</id><title>T</title>'
        '<link rel="self" href="https://b/self"/><updated>2026-01-01T00:00:00Z</updated></entry></feed>'
    )
    assert AtomParse().entries(feed, FEED) == (
        Entry(url="https://b/1", title="T", published_at="2026-01-01T00:00:00Z", text="", teaser=True),
    )


async def test_atom_page_reads_the_entry(web_page: str) -> None:
    entry = Entry(url="https://spanline.dev/", published_at="2026-10-27", text="feed text", teaser=True)
    read = AtomParse().page(entry, web_page)
    assert read.text.startswith("Spanline Spanline is an OpenTelemetry exporter")
    assert (read.teaser, read.links[1]) == (False, "https://github.com/spanline/spanline")


async def test_linkedin_entries_keep_the_authors_posts(profile_page: str) -> None:
    entries = LinkedinParse().entries(profile_page, PROFILE)
    assert [e.url for e in entries] == [
        "https://www.linkedin.com/pulse/traces-are-contract-ada-ledger-abcde",
        POST,
        "https://www.linkedin.com/posts/adavoice_evals-activity-2222222222222222222-EfGh",
    ]
    assert entries[0].title == entries[0].text == "Traces Are a Contract"
    assert (
        entries[1].title
        == "Spanline records every tool call of a coding agent as an OpenTelemetry span. 900 stars, MIT."
    )
    assert entries[1].teaser


async def test_linkedin_entries_login_wall() -> None:
    with pytest.raises(SweepError, match="no JSON-LD"):
        LinkedinParse().entries("<html><body>Sign in</body></html>", PROFILE)


async def test_linkedin_entries_node_named_by_its_id() -> None:
    page = (
        '<script type="application/ld+json">{"@type": "Article", "headline": "h", "@id": "urn:li:1",'
        ' "author": {"url": "https://www.linkedin.com/in/adavoice/"}}</script>'
    )
    (entry,) = LinkedinParse().entries(page, PROFILE)
    assert (entry.url, entry.title) == ("urn:li:1", "h")


async def test_linkedin_entries_node_without_a_url() -> None:
    page = (
        '<script type="application/ld+json">{"@type": "DiscussionForumPosting", "text": "t",'
        ' "author": {"url": "https://es.linkedin.com/in/adavoice"}, "mainEntityOfPage": {"@id": "x"}}</script>'
    )
    assert LinkedinParse().entries(page, PROFILE) == (
        Entry(url="x", title="t", published_at="", text="t", teaser=True),
    )


async def test_linkedin_page_reads_the_body_and_the_first_own_comment(post_page: str) -> None:
    entry = Entry(url=POST, published_at="2026-10-27T16:05:47.917Z", text="short", teaser=True)
    read = LinkedinParse().page(entry, post_page)
    assert read.text.startswith("Spanline records every tool call of a coding agent as an OpenTelemetry span. Each")
    assert read.text.endswith(
        "The author's first comment: Spanline is an OpenTelemetry exporter for agent harnesses. "
        "https://github.com/spanline/spanline"
    )
    assert (read.links, read.teaser) == (("https://github.com/spanline/spanline",), False)


@pytest.mark.parametrize(
    ("page", "text"),
    [
        ("<html>wall</html>", "short"),
        ('<script type="application/ld+json">{"@type": "SocialMediaPosting", "articleBody": "body"}</script>', "body"),
    ],
    ids=["no-post", "no-comment"],
)
async def test_linkedin_page_without_post_or_comment(page: str, text: str) -> None:
    entry = Entry(url=POST, published_at="", text="short", teaser=True)
    assert LinkedinParse().page(entry, page).text == text


async def test_web_entries_are_the_page_itself(web_page: str) -> None:
    (entry,) = WebParse().entries(web_page, SITE)
    assert (entry.url, entry.title, entry.published_at, entry.teaser) == (
        "https://spanline.dev/",
        "Spanline — agent spans",
        "2026-10-27T12:00:00+00:00",
        False,
    )
    assert WebParse().page(entry, "ignored") is entry
    assert not WebParse.deep
