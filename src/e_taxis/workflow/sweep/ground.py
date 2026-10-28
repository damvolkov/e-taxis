"""sweep.ground: the agents' findings kept only where a fetched page holds them — merged, re-fetched, ranked.

**Merge.** The same system named twice is one finding: first by its title (case and whitespace folded), then by
its primary link (a trailing slash aside). The members fold into the best-ranked one: its words stay, sources,
links, facts and entities are unioned, the relevance is the highest, the date the earliest, and a preferred
voice's `via` wins over the open web's. Two passes, each a dict: a finding that would bridge two groups only
through a non-primary link stays apart — the price of O(n) over a union-find nobody needs at this size.

**Ground.** Every distinct link is fetched once, under one gate. A link that does not answer is dropped from its
finding; a fact no answered page of its finding contains (case and whitespace folded) is dropped too. A finding
left without a link, or without a fact, does not survive: `notes` says which, and why.

**Rank.** Relevance first, highest on top; then vouching — a finding a preferred voice brought before the web's."""

import asyncio
from functools import reduce
from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Finding, Findings
from e_taxis.workflow.sweep.page import HtmlPage

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping

    from e_taxis.workflow.models.ports import WebPort

##### DEFAULTS #####
CONCURRENCY: int = 4


##### TYPES #####
class SweepGround:
    """Findings held to the pages they cite, over the web port."""

    __slots__ = ("_gate", "_web")

    def __init__(self, web: WebPort, concurrency: int = CONCURRENCY) -> None:
        self._web = web
        self._gate = asyncio.Semaphore(concurrency)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_rank(voices: Collection[str]) -> Callable[[Finding], tuple[int, bool]]:
        return lambda finding: (-finding.relevance, finding.via not in voices)

    @staticmethod
    def _merge_two(voices: Collection[str], kept: Finding, other: Finding) -> Finding:
        dates = sorted(date for date in (kept.published_at, other.published_at) if date)
        return msgspec.structs.replace(
            kept,
            facts=tuple(dict.fromkeys((*kept.facts, *other.facts))),
            links=tuple(dict.fromkeys((*kept.links, *other.links))),
            sources=tuple(dict.fromkeys((*kept.sources, *other.sources))),
            entities=tuple(dict.fromkeys((*kept.entities, *other.entities))),
            relevance=max(kept.relevance, other.relevance),
            published_at=dates[0] if dates else "",
            via=kept.via if kept.via in voices or other.via not in voices else other.via,
        )

    @classmethod
    def _merge_by(
        cls, findings: Iterable[Finding], key: Callable[[Finding], str], voices: Collection[str]
    ) -> list[Finding]:
        groups: dict[str, list[Finding]] = {}
        _ = [groups.setdefault(key(finding) or str(id(finding)), []).append(finding) for finding in findings]
        rank = cls._common_rank(voices)
        return [
            reduce(lambda kept, other: cls._merge_two(voices, kept, other), sorted(group, key=rank))
            for group in groups.values()
        ]

    async def _ground_page(self, url: str) -> tuple[str, str | None]:
        """A link and what its page holds, folded; None when it does not answer."""
        try:
            async with self._gate:
                body = await self._web.get(url)
        except SweepError:
            return url, None
        return url, HtmlPage.normal(HtmlPage.read(url, body).strings)

    @staticmethod
    def _ground_one(finding: Finding, pages: Mapping[str, str | None]) -> Finding | str:
        """The finding cut to what its pages hold, or why it does not survive."""
        answered = {link: page for link in finding.links if (page := pages[link]) is not None}
        facts = tuple(
            fact for fact in finding.facts if any(HtmlPage.normal(fact) in page for page in answered.values())
        )
        match (bool(answered), bool(facts)):
            case (False, _):
                return f"{finding.title}: no link answered"
            case (_, False):
                return f"{finding.title}: no fact on its pages"
            case _:
                return msgspec.structs.replace(finding, links=tuple(answered), facts=facts)

    ############################################################

    ##### PUBLIC #####

    async def ground(self, sides: Iterable[Findings], voices: Collection[str]) -> Findings:
        """Every side's findings, merged, grounded and ranked; `voices` are the preferred voices' ids."""
        told = [finding for side in sides for finding in side.findings]
        named = self._merge_by(told, lambda finding: HtmlPage.normal(finding.title), voices)
        merged = self._merge_by(named, lambda finding: finding.links[0].rstrip("/") if finding.links else "", voices)
        links = {link for finding in merged for link in finding.links}
        async with asyncio.TaskGroup() as group:
            fetched = [group.create_task(self._ground_page(link)) for link in sorted(links)]
        pages = dict(task.result() for task in fetched)
        judged = [self._ground_one(finding, pages) for finding in merged]
        kept = sorted((found for found in judged if isinstance(found, Finding)), key=self._common_rank(voices))
        dropped = [found for found in judged if isinstance(found, str)]
        return Findings(findings=tuple(kept), notes=" · ".join((f"ground: {len(kept)} of {len(told)} kept", *dropped)))
