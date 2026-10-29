"""sweep.frame: what a sweep looks at — radar.yaml's plane narrowed to a topic, the window as dates, the voices first.

A topic narrows the plane to its keywords and to the voices and links that speak to it (their `topics` name it,
or `*`); no topic is the whole plane, every topic's keywords. The window counts calendar days back from `today`,
both ends inclusive. A run's extra voices are URLs: the kind is read off the URL alone — a LinkedIn `/in/` profile,
a feed path (`/feed`, `/atom`, `/rss`, `.xml`, `.atom`, `.rss`), else the page itself — and the id is the URL
without its scheme. A voice or link already in radar.yaml is not added twice. An unknown topic stops the run here."""

import datetime as dt
import re
from typing import TYPE_CHECKING, Final, Self

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Frame, RadarConfig, Voice, VoiceKind

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
RADAR: str = "core/tekton/config/radar.yaml"
ALL: str = "*"
KINDS: Final[tuple[tuple[re.Pattern[str], VoiceKind], ...]] = (
    (re.compile(r"linkedin\.com/in/[^/]+/?$"), VoiceKind.LINKEDIN_PROFILE),
    (re.compile(r"(/feed|/atom|/rss|\.xml|\.atom|\.rss)/?$"), VoiceKind.ATOM_FEED),
)


##### TYPES #####
class SweepFrame:
    """One radar.yaml, fixed into frames."""

    __slots__ = ("_config",)

    def __init__(self, config: RadarConfig) -> None:
        self._config = config

    ##### PRIVATE METHODS #####

    @staticmethod
    def _fix_speaks(topics: tuple[str, ...], topic: str) -> bool:
        return not topic or ALL in topics or topic in topics

    @staticmethod
    def _fix_extra(url: str, topic: str) -> Voice:
        kind = next((kind for pattern, kind in KINDS if pattern.search(url)), VoiceKind.WEB)
        return Voice(id=url.split("://", 1)[-1].rstrip("/"), url=url, kind=kind, topics=(topic or ALL,))

    def _fix_window(self, window: str) -> int:
        match window:
            case "":
                return self._config.window
            case days if days.isdigit():
                return int(days)
            case _:
                msg = f"window {window!r} is not a whole number of days"
                raise SweepError(msg)

    def _fix_keywords(self, topic: str) -> tuple[str, ...]:
        match self._config.topics.get(topic):
            case None if topic:
                msg = f"unknown topic {topic!r}: radar.yaml knows {', '.join(self._config.topics)}"
                raise SweepError(msg)
            case None:
                return tuple(dict.fromkeys(word for found in self._config.topics.values() for word in found.keywords))
            case found:
                return found.keywords

    ############################################################

    ##### PUBLIC #####

    @classmethod
    async def load(cls, nous: Path) -> Self:
        """The checkout's radar.yaml, read through its model."""
        try:
            text = await anyio.Path(nous / RADAR).read_text()
        except FileNotFoundError as missing:
            msg = f"no radar.yaml at {nous / RADAR}"
            raise SweepError(msg) from missing
        try:
            return cls(msgspec.convert(eserde.loads(text, format=eserde.Format.YAML), RadarConfig))
        except (eserde.LoadError, msgspec.ValidationError) as bad:
            msg = f"radar.yaml does not fit its schema: {bad}"
            raise SweepError(msg) from bad

    @property
    def config(self) -> RadarConfig:
        return self._config

    def fix(self, *, today: dt.date, topic: str = "", window: str = "", authors: str = "", links: str = "") -> Frame:
        """The frame of one run: `authors` and `links` are its extras, space-separated."""
        keywords = self._fix_keywords(topic)
        heard = [
            Voice(id=key, name=author.name, url=author.url, kind=author.kind, topics=author.topics)
            for key, author in self._config.authors.items()
            if self._fix_speaks(author.topics, topic)
        ]
        known = {voice.url.rstrip("/") for voice in heard}
        extras = {
            url.rstrip("/"): self._fix_extra(url, topic) for url in authors.split() if url.rstrip("/") not in known
        }
        listed = (link.url for link in self._config.links.values() if self._fix_speaks(link.topics, topic))
        return Frame(
            brief=self._config.brief,
            topic=topic,
            keywords=keywords,
            since=(today - dt.timedelta(days=self._fix_window(window))).isoformat(),
            until=today.isoformat(),
            voices=(*heard, *extras.values()),
            links=tuple(dict.fromkeys((*listed, *links.split()))),
        )
