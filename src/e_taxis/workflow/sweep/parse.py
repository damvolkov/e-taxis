"""sweep.parse: one parser per voice kind, chosen from a frozen table — what a voice's listing holds, then each entry.

`entries` reads the voice's own listing into entries marked `teaser` (only the listing's text is known); `page`
reads one entry's fetched page into the entry whose body was read. Where the listing is the page itself (`web`),
there is nothing deeper to fetch: `deep` is false and `page` keeps the entry as it is.

- **atom_feed**: the feed's XML, through the stdlib's parser (expat refuses entity expansion bombs); each `entry`'s
  alternate link, date (published, else updated), title and content as text. The entry's page: its visible text.
- **linkedin_profile**: the public profile's JSON-LD — the posts and articles whose author is the profile (a
  repost by someone else is not the voice's). A page with no JSON-LD at all is a login wall or a new layout: an
  error, never an empty window. The post's page: its `SocialMediaPosting` — the full body, and the author's own
  first comment (by date), where the project link usually lives.
- **web**: the page itself, one entry — its title, its date when it states one, its text and links."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final, Protocol
from urllib.parse import urlsplit
from xml.etree import ElementTree

import msgspec

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Entry, Voice, VoiceKind
from e_taxis.workflow.sweep.page import HtmlPage

if TYPE_CHECKING:
    from collections.abc import Mapping
    from xml.etree.ElementTree import Element

##### DEFAULTS #####
ATOM: str = "{http://www.w3.org/2005/Atom}"
POSTS: Final[frozenset[str]] = frozenset({"DiscussionForumPosting", "SocialMediaPosting", "Article"})
TITLE: int = 120
COMMENT: str = "The author's first comment: "


##### TYPES #####
class KindParse(Protocol):
    """What fetch asks of a voice kind's parser."""

    deep: ClassVar[bool]

    def entries(self, body: str, voice: Voice) -> tuple[Entry, ...]: ...

    def page(self, entry: Entry, body: str) -> Entry: ...


class AtomParse:
    __slots__ = ()

    deep: ClassVar[bool] = True

    ##### PRIVATE METHODS #####

    @staticmethod
    def _entries_one(node: Element) -> Entry:
        alternate = (
            link.get("href", "") for link in node.iter(f"{ATOM}link") if link.get("rel", "alternate") == "alternate"
        )
        url = next(alternate, "") or (node.findtext(f"{ATOM}id") or "").strip()
        body = node.findtext(f"{ATOM}content") or node.findtext(f"{ATOM}summary") or ""
        page = HtmlPage.read(url, body)
        return Entry(
            url=url,
            title=(node.findtext(f"{ATOM}title") or "").strip(),
            published_at=(node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated") or "").strip(),
            text=page.text,
            links=page.links,
            teaser=True,
        )

    ############################################################

    ##### PUBLIC #####

    def entries(self, body: str, voice: Voice) -> tuple[Entry, ...]:
        try:
            root = ElementTree.fromstring(body)  # noqa: S314 — expat ≥ 2.4 refuses entity expansion bombs; no DTD is fetched.
        except ElementTree.ParseError as bad:
            msg = f"{voice.url}: not an Atom feed ({bad})"
            raise SweepError(msg) from bad
        match root.tag:
            case "{http://www.w3.org/2005/Atom}feed":
                return tuple(self._entries_one(node) for node in root.iter(f"{ATOM}entry"))
            case tag:
                msg = f"{voice.url}: not an Atom feed (its root is <{tag}>)"
                raise SweepError(msg)

    def page(self, entry: Entry, body: str) -> Entry:
        page = HtmlPage.read(entry.url, body)
        return msgspec.structs.replace(entry, text=page.text, links=page.links, teaser=False)


class LinkedinParse:
    __slots__ = ()

    deep: ClassVar[bool] = True

    ##### PRIVATE METHODS #####

    @staticmethod
    def _entries_handle(url: object) -> str:
        """The profile a URL names: `/in/<handle>` on any of LinkedIn's country hosts."""
        return urlsplit(str(url)).path.rstrip("/").rsplit("/", 1)[-1]

    @staticmethod
    def _entries_url(node: Mapping[str, Any]) -> str:
        match node:
            case {"url": str() as url}:
                return url
            case {"mainEntityOfPage": str() as url} | {"mainEntityOfPage": {"@id": str() as url}}:
                return url
            case _:
                return str(node.get("@id", ""))

    @classmethod
    def _entries_one(cls, node: Mapping[str, Any]) -> Entry:
        text = str(node.get("text") or node.get("articleBody") or node.get("headline") or "")
        return Entry(
            url=cls._entries_url(node),
            title=str(node.get("headline") or text.split("\n", 1)[0][:TITLE]),
            published_at=str(node.get("datePublished", "")),
            text=text,
            links=HtmlPage.urls(text),
            teaser=True,
        )

    @staticmethod
    def _page_comment(node: Mapping[str, Any]) -> str:
        """The author's own first comment on the post, by date; empty when the author left none."""
        author = (node.get("author") or {}).get("name", "")
        own = [c for c in node.get("comment") or () if (c.get("author") or {}).get("name") == author and author]
        first = min(own, key=lambda comment: str(comment.get("datePublished", "")), default={})
        return str(first.get("text", ""))

    ############################################################

    ##### PUBLIC #####

    def entries(self, body: str, voice: Voice) -> tuple[Entry, ...]:
        page = HtmlPage.read(voice.url, body)
        match page.ld:
            case ():
                msg = f"{voice.url}: no JSON-LD on the page — a login wall, or LinkedIn changed its layout"
                raise SweepError(msg)
            case nodes:
                handle = self._entries_handle(voice.url)
                return tuple(
                    self._entries_one(node)
                    for node in nodes
                    if node.get("@type") in POSTS
                    and self._entries_handle((node.get("author") or {}).get("url")) == handle
                )

    def page(self, entry: Entry, body: str) -> Entry:
        posts = (n for n in HtmlPage.read(entry.url, body).ld if n.get("@type") in POSTS and n.get("articleBody"))
        match next(posts, None):
            case None:
                return entry
            case node:
                comment = self._page_comment(node)
                text = f"{node['articleBody']}\n\n{COMMENT}{comment}" if comment else str(node["articleBody"])
                return msgspec.structs.replace(entry, text=text, links=HtmlPage.urls(text), teaser=False)


class WebParse:
    __slots__ = ()

    deep: ClassVar[bool] = False

    def entries(self, body: str, voice: Voice) -> tuple[Entry, ...]:
        page = HtmlPage.read(voice.url, body)
        return (Entry(url=voice.url, title=page.title, published_at=page.published, text=page.text, links=page.links),)

    def page(self, entry: Entry, body: str) -> Entry:  # noqa: ARG002 — the listing is the page: nothing deeper to read.
        return entry


##### THE TABLE #####
PARSERS: Final[Mapping[VoiceKind, KindParse]] = MappingProxyType(
    {VoiceKind.ATOM_FEED: AtomParse(), VoiceKind.LINKEDIN_PROFILE: LinkedinParse(), VoiceKind.WEB: WebParse()}
)
