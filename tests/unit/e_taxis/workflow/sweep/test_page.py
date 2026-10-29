"""tests/unit/e_taxis/workflow/sweep/page: an HTML page read once — text without scripts, absolute links, JSON-LD."""

import pytest

from e_taxis.workflow.sweep.page import HtmlPage


async def test_page_text_skips_what_no_reader_sees(web_page: str) -> None:
    page = HtmlPage.read("https://spanline.dev/", web_page)
    assert (
        page.text
        == "Spanline Spanline is an OpenTelemetry exporter for agent harnesses & coding agents. Docs Source Source again Mail Top"
    )
    assert page.title == "Spanline — agent spans"
    assert page.published == "2026-10-27T12:00:00+00:00"


async def test_page_links_are_absolute_once_each(web_page: str) -> None:
    assert HtmlPage.read("https://spanline.dev/", web_page).links == (
        "https://spanline.dev/docs/",
        "https://github.com/spanline/spanline",
        "https://spanline.dev/",
    )


async def test_page_ld_flattens_the_graph(profile_page: str) -> None:
    page = HtmlPage.read("https://www.linkedin.com/in/adavoice", profile_page)
    assert [node["@type"] for node in page.ld] == [
        "Article",
        "DiscussionForumPosting",
        "DiscussionForumPosting",
        "DiscussionForumPosting",
        "WebPage",
        "Person",
    ]
    assert page.published == "2026-10-27T09:00:00.000+00:00"


@pytest.mark.parametrize(
    ("block", "types"),
    [
        ('[{"@type": "A"}, 3]', ["A"]),
        ('{"@type": "B"}', ["B"]),
        ("not json", []),
        ("7", []),
    ],
    ids=["list", "object", "broken", "scalar"],
)
async def test_page_ld_block_shapes(block: str, types: list[str]) -> None:
    page = HtmlPage.read("https://x/", f'<script type="application/ld+json">{block}</script>')
    assert [node["@type"] for node in page.ld] == types


async def test_page_strings_hold_text_and_ld(post_page: str) -> None:
    strings = HtmlPage.read("https://www.linkedin.com/posts/x", post_page).strings
    assert "https://github.com/spanline/spanline" in strings
    assert "Each span carries the prompt hash" in strings


async def test_page_without_date_or_title() -> None:
    page = HtmlPage.read("https://x/", "<p>bare</p><meta name='other' content='1'>")
    assert (page.published, page.title, page.text) == ("", "", "bare")


@pytest.mark.parametrize(
    ("text", "urls"),
    [
        ("see https://a.dev/x. and (https://b.dev/y), again https://a.dev/x", ("https://a.dev/x", "https://b.dev/y")),
        ("no link", ()),
    ],
    ids=["prose", "none"],
)
async def test_page_urls_in_prose(text: str, urls: tuple[str, ...]) -> None:
    assert HtmlPage.urls(text) == urls


async def test_page_normal_folds_case_and_space() -> None:
    assert HtmlPage.normal("  Spans\n  CARRY  costs ") == "spans carry costs"
