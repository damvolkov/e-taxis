"""sweep.page: one HTML page read once, with the stdlib's parser — its visible text, its links, its JSON-LD.

What a reader sees is the text outside `script`, `style` and their kin; what a publisher states about the page
(LinkedIn's posts and comments, an article's date) lives in its `application/ld+json` blocks, kept as nodes — a
block holding an `@graph` gives its nodes, a list its items, an object itself. A block that is not JSON is dropped:
the page is evidence, never trusted to be well-formed. Links are absolute http(s) URLs, once each, in page order."""

import json
import re
from enum import StrEnum
from html.parser import HTMLParser
from typing import Any, Final
from urllib.parse import urljoin, urlsplit

##### DEFAULTS #####
HIDDEN: Final[frozenset[str]] = frozenset({"script", "style", "noscript", "template", "svg"})
LD: str = "application/ld+json"
PUBLISHED: Final[frozenset[str]] = frozenset({"article:published_time", "datePublished", "date"})
SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
### a URL in prose ends before whitespace, a quote or a closing bracket; trailing punctuation is the sentence's.
URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")
TRAIL: str = ".,;:!?"


##### TYPES #####
class PageZone(StrEnum):
    """Where the parser stands: in the text, inside a JSON-LD block, or in the title."""

    TEXT = ""
    LD = "ld"
    TITLE = "title"


class HtmlPage(HTMLParser):
    """Fed once by `read`; afterwards a value: `text`, `links`, `title`, `published`, `ld`, `strings`."""

    def __init__(self, url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._url = url
        self._words: list[str] = []
        self._title: list[str] = []
        self._links: dict[str, None] = {}
        self._blocks: list[list[str]] = []
        self._meta = ""
        self._hidden = 0
        self._where = PageZone.TEXT

    ##### PRIVATE METHODS #####

    def _read_link(self, href: str) -> None:
        url = urljoin(self._url, href).split("#", 1)[0]
        self._links |= {url: None} if urlsplit(url).scheme in SCHEMES else {}

    def _read_meta(self, attrs: dict[str, str | None]) -> None:
        name = attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or ""
        self._meta = self._meta or (attrs.get("content") or "" if name in PUBLISHED else "")

    @staticmethod
    def _ld_nodes(raw: str) -> list[dict[str, Any]]:
        try:
            block = json.loads(raw)
        except json.JSONDecodeError:
            return []
        match block:
            case {"@graph": list() as graph}:
                return [node for node in graph if isinstance(node, dict)]
            case list():
                return [node for node in block if isinstance(node, dict)]
            case dict():
                return [block]
            case _:
                return []

    @classmethod
    def _strings_of(cls, value: object) -> list[str]:
        match value:
            case str():
                return [value]
            case dict():
                return [found for item in value.values() for found in cls._strings_of(item)]
            case list():
                return [found for item in value for found in cls._strings_of(item)]
            case _:
                return []

    ############################################################

    ##### PUBLIC #####

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        match tag:
            case "script" if found.get("type") == LD:
                self._blocks.append([])
                self._where = PageZone.LD
            case "title":
                self._where = PageZone.TITLE
            case "a" if href := found.get("href"):
                self._read_link(href)
            case "meta":
                self._read_meta(found)
            case _:
                pass
        self._hidden += tag in HIDDEN

    def handle_endtag(self, tag: str) -> None:
        self._hidden -= tag in HIDDEN and self._hidden > 0
        self._where = PageZone.TEXT if tag in {"script", "title"} else self._where

    def handle_data(self, data: str) -> None:
        match self._where:
            case PageZone.LD:
                self._blocks[-1].append(data)
            case PageZone.TITLE:
                self._title.append(data)
            case _ if not self._hidden:
                self._words.append(data)
            case _:
                pass

    @classmethod
    def read(cls, url: str, html: str) -> HtmlPage:
        """The page at `url` (the base its relative links resolve against), parsed."""
        page = cls(url)
        page.feed(html)
        page.close()
        return page

    @staticmethod
    def normal(text: str) -> str:
        """Case and whitespace folded: what grounding compares."""
        return " ".join(text.casefold().split())

    @staticmethod
    def urls(text: str) -> tuple[str, ...]:
        """Every http(s) URL written in prose, once each, in order."""
        return tuple(dict.fromkeys(found.rstrip(TRAIL) for found in URL.findall(text)))

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._words).split())

    @property
    def title(self) -> str:
        return " ".join("".join(self._title).split())

    @property
    def links(self) -> tuple[str, ...]:
        return tuple(self._links)

    @property
    def ld(self) -> tuple[dict[str, Any], ...]:
        return tuple(node for block in self._blocks for node in self._ld_nodes("".join(block)))

    @property
    def published(self) -> str:
        """The date the page says it was published: its meta tag, else its first JSON-LD date; empty when neither."""
        dated = (str(node["datePublished"]) for node in self.ld if node.get("datePublished"))
        return self._meta or next(dated, "")

    @property
    def strings(self) -> str:
        """The visible text and every string the JSON-LD states: all a fetched page holds, as text."""
        return " ".join((self.text, *(found for node in self.ld for found in self._strings_of(node))))
