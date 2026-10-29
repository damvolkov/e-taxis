"""sweep.fetch: every voice of the frame read with its kind's parser, its window kept, each entry's page fetched.

Voices are read at once, under one gate that bounds every request in flight. A voice whose listing does not
answer or does not parse is a row with status `error` and the reason — never dropped; a window that held nothing
is `empty`. Inside the window means the entry's date, as a calendar day in Europe/Madrid, falls between the
frame's `since` and `until`, both inclusive; an entry that states no readable date cannot be ruled out, so it is
kept. An entry whose own page does not answer keeps the listing's text, marked `teaser`. `new`: its URL is not
in the ledger under its voice."""

import asyncio
import datetime as dt
from typing import TYPE_CHECKING, Final
from zoneinfo import ZoneInfo

import msgspec

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Entries, Entry, Frame, Seen, Voice, VoiceEntries, VoiceStatus
from e_taxis.workflow.sweep.parse import PARSERS

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import WebPort
    from e_taxis.workflow.sweep.parse import KindParse

##### DEFAULTS #####
ZONE: Final[ZoneInfo] = ZoneInfo("Europe/Madrid")
CONCURRENCY: int = 4


##### TYPES #####
class SweepFetch:
    """The frame's voices over the web port, at most `concurrency` requests in flight."""

    __slots__ = ("_gate", "_web")

    def __init__(self, web: WebPort, concurrency: int = CONCURRENCY) -> None:
        self._web = web
        self._gate = asyncio.Semaphore(concurrency)

    ##### PRIVATE METHODS #####

    async def _common_get(self, url: str) -> str:
        async with self._gate:
            return await self._web.get(url)

    @staticmethod
    def _fetch_day(published: str) -> dt.date | None:
        """The calendar day in Madrid an ISO stamp names (a naive one is UTC); None when it names none."""
        try:
            stamp = dt.datetime.fromisoformat(published)
        except ValueError:
            return None
        return (stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.UTC)).astimezone(ZONE).date()

    @classmethod
    def _fetch_inside(cls, entry: Entry, frame: Frame) -> bool:
        day = cls._fetch_day(entry.published_at)
        return day is None or dt.date.fromisoformat(frame.since) <= day <= dt.date.fromisoformat(frame.until)

    async def _fetch_page(self, parser: KindParse, entry: Entry) -> Entry:
        match parser.deep:
            case False:
                return entry
            case _:
                try:
                    body = await self._common_get(entry.url)
                except SweepError:
                    return entry
                return parser.page(entry, body)

    async def _fetch_voice(self, voice: Voice, frame: Frame, seen: Seen) -> VoiceEntries:
        parser = PARSERS[voice.kind]
        try:
            listed = parser.entries(await self._common_get(voice.url), voice)
        except SweepError as failed:
            return VoiceEntries(id=voice.id, status=VoiceStatus.ERROR, error=str(failed))
        known = seen.seen.get(voice.id, {})
        inside = [
            msgspec.structs.replace(entry, new=entry.url not in known)
            for entry in listed
            if self._fetch_inside(entry, frame)
        ]
        async with asyncio.TaskGroup() as group:
            pages = [group.create_task(self._fetch_page(parser, entry)) for entry in inside]
        read = tuple(page.result() for page in pages)
        return VoiceEntries(
            id=voice.id,
            status=VoiceStatus.OK if read else VoiceStatus.EMPTY,
            parsed=len(listed),
            in_window=len(read),
            new=sum(entry.new for entry in read),
            entries=read,
        )

    ############################################################

    ##### PUBLIC #####

    async def fetch(self, frame: Frame, seen: Seen) -> Entries:
        async with asyncio.TaskGroup() as group:
            voices = [group.create_task(self._fetch_voice(voice, frame, seen)) for voice in frame.voices]
        return Entries(voices=tuple(voice.result() for voice in voices))
