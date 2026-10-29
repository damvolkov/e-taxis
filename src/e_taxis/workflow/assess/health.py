"""assess.health: the candidate's health from no-auth sources, dated — flow-gen-research's KPIs, no model.

GitHub's REST API gives the licence, the contributors (the `last` page of a one-per-page listing), the open-issue
ratio (two counts from the search API) and, for a repository with no registry, the releases; deps.dev gives the
OpenSSF Scorecard of the repository and, for a package, every published version (the cadence) and the dependents of
the default one — crates.io's own reverse dependencies for a crate, where deps.dev counts none. Downloads come from
pypistats, npm's downloads API or crates.io's daily series, as the registry dictates. Every source is read
concurrently; one that fails leaves its fields null and is named in `failed` — never guessed. A cadence read off a
page of releases that is full and all within the year is extrapolated over the page's span, and said so."""

import asyncio
import datetime as dt
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote

import msgspec

from e_taxis.workflow.models.assess import Candidate, Fetched, Health, Registry

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping

    from e_taxis.workflow.models.ports import ApiPort

##### DEFAULTS #####
GITHUB: str = "https://api.github.com"
DEPS: str = "https://api.deps.dev"
SEARCH: str = GITHUB + "/search/issues?q=repo:{repo}+type:issue{state}&per_page=1"
PAGE: int = 100
### release pages read at most: 500 releases a year is past any cadence threshold already.
PAGES: int = 5
YEAR: dt.timedelta = dt.timedelta(days=365)
MONTH: dt.timedelta = dt.timedelta(days=30)
LAST: Final[re.Pattern[str]] = re.compile(r'[?&]page=(\d+)>;\s*rel="last"')
SYSTEMS: Final[Mapping[Registry, str]] = MappingProxyType(
    {Registry.PYPI: "pypi", Registry.NPM: "npm", Registry.CRATES: "cargo"}
)
DOWNLOADS: Final[Mapping[Registry, str]] = MappingProxyType(
    {
        Registry.PYPI: "https://pypistats.org/api/packages/{name}/recent",
        Registry.NPM: "https://api.npmjs.org/downloads/point/last-month/{name}",
        Registry.CRATES: "https://crates.io/api/v1/crates/{name}/downloads",
    }
)


##### UTILITIES #####
def downloads_pypi(body: Any, _now: dt.datetime) -> int | None:
    match body:
        case {"data": {"last_month": int() as month}}:
            return month
        case _:
            return None


def downloads_npm(body: Any, _now: dt.datetime) -> int | None:
    match body:
        case {"downloads": int() as month}:
            return month
        case _:
            return None


def downloads_crates(body: Any, now: dt.datetime) -> int | None:
    """The daily series' last 30 days: every version's rows plus the rows of versions crates.io no longer lists."""
    match body:
        case {"version_downloads": list() as rows, "meta": {"extra_downloads": list() as extra}}:
            since = (now - MONTH).date().isoformat()
            return sum(int(row["downloads"]) for row in (*rows, *extra) if str(row["date"]) > since)
        case _:
            return None


READERS: Final[Mapping[Registry, Callable[[Any, dt.datetime], int | None]]] = MappingProxyType(
    {Registry.PYPI: downloads_pypi, Registry.NPM: downloads_npm, Registry.CRATES: downloads_crates}
)


##### TYPES #####
@dataclass(frozen=True, slots=True)
class Reading:
    """What one source said: the fields it measured, the URL each came from, and what it could not give."""

    fields: dict[str, object] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    failed: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class AssessHealth:
    """Satisfies nothing; reads public APIs through ApiPort and never raises for a source that failed."""

    __slots__ = ("_api",)

    def __init__(self, api: ApiPort) -> None:
        self._api = api

    ##### PRIVATE METHODS #####

    async def _common_json(self, url: str, *fields: str) -> tuple[Fetched, Any, Reading]:
        """The body of `url` decoded, or the Reading naming `fields` as failed with the reason."""
        fetched = await self._api.get(url)
        match fetched.ok:
            case True:
                return fetched, msgspec.json.decode(fetched.body), Reading()
            case _:
                why = f"{url} → {fetched.status or fetched.error}"
                return fetched, None, Reading(failed=tuple(f"{name}: {why}" for name in fields))

    @staticmethod
    def _common_said(names: tuple[str, ...], values: tuple[object, ...], url: str) -> Reading:
        """The fields that have a value, sourced at `url`; the ones that do not, failed as an unexpected shape."""
        kept = {name: value for name, value in zip(names, values, strict=True) if value is not None}
        missing = tuple(f"{name}: {url} → unexpected shape" for name in names if name not in kept)
        return Reading(fields=kept, sources=dict.fromkeys(kept, url), failed=missing)

    @staticmethod
    def _common_cadence(
        dates: list[dt.datetime], now: dt.datetime, since: dt.datetime | None
    ) -> tuple[str, float, tuple[str, ...]]:
        """(last release, releases per year, notes). `since` None: the listing is whole, the year is counted; else
        the listing stops at `since`, short of a year, and the rate is extrapolated over that window."""
        last = max(dates).isoformat()
        match since:
            case None:
                return last, float(sum(date >= now - YEAR for date in dates)), ()
            case start:
                window = max((now - start).total_seconds(), 1.0)
                rate = round(sum(date >= start for date in dates) * YEAR.total_seconds() / window, 1)
                return last, rate, (f"cadence extrapolated over the {window / 86400:.0f} days the listing reached",)

    async def _measure_license(self, repo: str) -> Reading:
        url = f"{GITHUB}/repos/{repo}"
        _, body, failed = await self._common_json(url, "license")
        match body:
            case {"license": {"spdx_id": str() as spdx}}:
                return Reading(fields={"license": spdx}, sources={"license": url})
            case None:
                return failed
            case _:
                return Reading(failed=(f"license: {url} → no licence declared",))

    async def _measure_contributors(self, repo: str) -> Reading:
        url = f"{GITHUB}/repos/{repo}/contributors?per_page=1&anon=true"
        fetched, body, failed = await self._common_json(url, "contributors")
        match (LAST.search(fetched.link), body):
            case (_, None):
                return failed
            case (re.Match() as last, _):
                return self._common_said(("contributors",), (int(last.group(1)),), url)
            case (_, list() as listing):
                return self._common_said(("contributors",), (len(listing),), url)
            case _:
                return self._common_said(("contributors",), (None,), url)

    async def _measure_issues(self, repo: str) -> Reading:
        urls = (SEARCH.format(repo=repo, state="+state:open"), SEARCH.format(repo=repo, state=""))
        (_, opened, failed), (_, every, also) = [await self._common_json(url, "open_issue_ratio") for url in urls]
        match (opened, every):
            case ({"total_count": int() as now_open}, {"total_count": int() as total}) if total:
                return self._common_said(("open_issue_ratio",), (round(now_open / total, 4),), urls[1])
            case (None, _) | (_, None):
                return Reading(failed=(*failed.failed, *also.failed))
            case _:
                return Reading(failed=(f"open_issue_ratio: {urls[1]} → no issue ever opened",))

    async def _measure_scorecard(self, repo: str) -> Reading:
        url = f"{DEPS}/v3/projects/{quote(f'github.com/{repo}', safe='')}"
        _, body, failed = await self._common_json(url, "scorecard")
        match body:
            case {"scorecard": {"overallScore": int() | float() as score, "date": str() as date}}:
                return Reading(
                    fields={"scorecard": float(score)}, sources={"scorecard": url}, notes=(f"scorecard of {date}",)
                )
            case None:
                return failed
            case _:
                return Reading(failed=(f"scorecard: {url} → deps.dev holds no Scorecard for {repo}",))

    async def _releases_pages(self, repo: str, now: dt.datetime, page: int = 1) -> tuple[list[Any], str]:
        """Every release page down to a year back, at most PAGES; the failure of the first page that failed."""
        url = f"{GITHUB}/repos/{repo}/releases?per_page={PAGE}&page={page}"
        _, body, failed = await self._common_json(url, "releases")
        match body:
            case [*releases] if (
                len(releases) == PAGE
                and page < PAGES
                and min(dt.datetime.fromisoformat(str(r["created_at"])) for r in releases) >= now - YEAR
            ):
                more, failure = await self._releases_pages(repo, now, page + 1)
                return [*releases, *more], failure
            case [*releases]:
                return releases, ""
            case _:
                return [], failed.failed[0].partition(": ")[2] if failed.failed else "unexpected shape"

    async def _measure_releases(self, repo: str, now: dt.datetime) -> Reading:
        """A repository with no registry: its GitHub releases down to a year back — stable ones only (no draft, no
        pre-release); a listing capped short of a year gives a rate over the window it reached."""
        url = f"{GITHUB}/repos/{repo}/releases"
        names = ("last_release", "releases_per_year")
        releases, failure = await self._releases_pages(repo, now)
        stable = [r for r in releases if r.get("published_at") and not r.get("prerelease") and not r.get("draft")]
        dates = [dt.datetime.fromisoformat(str(r["published_at"])) for r in stable]
        created = [dt.datetime.fromisoformat(str(r["created_at"])) for r in releases]
        reached = min(created) if created and len(releases) == PAGE * PAGES and min(created) >= now - YEAR else None
        skipped = (
            (f"{len(releases) - len(stable)} pre-releases and drafts not counted",)
            if len(stable) < len(releases)
            else ()
        )
        match (dates, failure):
            case ([_, *_], ""):
                last, rate, notes = self._common_cadence(dates, now, reached)
                return Reading(
                    fields={"last_release": last, "releases_per_year": rate},
                    sources=dict.fromkeys(names, url),
                    notes=(*notes, *skipped),
                )
            case (_, str() as why) if why:
                return Reading(failed=tuple(f"{name}: {why}" for name in names))
            case _:
                return Reading(failed=tuple(f"{name}: {url} → no stable release published" for name in names))

    async def _measure_dependents(self, registry: Registry, name: str, version: str) -> Reading:
        """crates.io's reverse dependencies for a crate; deps.dev's dependents of the default version otherwise."""
        package = quote(name, safe="")
        url = (
            f"https://crates.io/api/v1/crates/{package}/reverse_dependencies?per_page=1"
            if registry is Registry.CRATES
            else f"{DEPS}/v3alpha/systems/{SYSTEMS[registry]}/packages/{package}/versions/{quote(version)}:dependents"
        )
        _, body, failed = await self._common_json(url, "dependents")
        match body:
            case {"meta": {"total": int() as count}} | {"dependentCount": int() as count}:
                return self._common_said(("dependents",), (count,), url)
            case None:
                return failed
            case _:
                return self._common_said(("dependents",), (None,), url)

    async def _measure_versions(self, registry: Registry, name: str, now: dt.datetime) -> Reading:
        """Every published version (the cadence), then the dependents of the default one."""
        url = f"{DEPS}/v3/systems/{SYSTEMS[registry]}/packages/{quote(name, safe='')}"
        names = ("last_release", "releases_per_year")
        _, body, failed = await self._common_json(url, *names, "dependents")
        match body:
            case {"versions": [*versions]} if dates := [
                dt.datetime.fromisoformat(str(v["publishedAt"])) for v in versions if v.get("publishedAt")
            ]:
                default = next((v["versionKey"]["version"] for v in versions if v.get("isDefault")), "")
                last, rate, notes = self._common_cadence(dates, now, None)
                dependents = await self._measure_dependents(registry, name, default)
                return Reading(
                    fields={"last_release": last, "releases_per_year": rate, **dependents.fields},
                    sources=dict.fromkeys(names, url) | dependents.sources,
                    failed=dependents.failed,
                    notes=notes,
                )
            case None:
                return failed
            case _:
                return Reading(failed=tuple(f"{key}: {url} → no version listed" for key in (*names, "dependents")))

    async def _measure_downloads(self, registry: Registry, name: str, now: dt.datetime) -> Reading:
        url = DOWNLOADS[registry].format(name=quote(name, safe="@"))
        _, body, failed = await self._common_json(url, "downloads_month")
        return failed if body is None else self._common_said(("downloads_month",), (READERS[registry](body, now),), url)

    def _measure_sources(self, candidate: Candidate, now: dt.datetime) -> list[Coroutine[Any, Any, Reading]]:
        """The readings the candidate allows: the repository's, and the registry's — or, with none, the releases'."""
        repo, name = candidate.repo, candidate.package
        github = (
            [
                self._measure_license(repo),
                self._measure_contributors(repo),
                self._measure_issues(repo),
                self._measure_scorecard(repo),
            ]
            if repo
            else []
        )
        match (candidate.registry, repo):
            case (Registry() as registry, _) if name:
                published = [self._measure_versions(registry, name, now), self._measure_downloads(registry, name, now)]
            case (_, str() as source) if source:
                published = [self._measure_releases(source, now)]
            case _:
                published = []
        return [*github, *published]

    ############################################################

    ##### PUBLIC #####

    async def measure(self, candidate: Candidate, now: dt.datetime) -> Health:
        """Every KPI the candidate's sources give, measured at `now`."""
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(source) for source in self._measure_sources(candidate, now)]
        readings = [task.result() for task in tasks]
        blind = (
            () if candidate.repo else ("no repository: licence, contributors, issues and Scorecard unmeasured",)
        ) + (() if candidate.registry else ("no registry: downloads and dependents unmeasured",))
        merged = {key: value for reading in readings for key, value in reading.fields.items()}
        return msgspec.convert(
            {
                "measured_at": now.isoformat(),
                **merged,
                "sources": {key: url for reading in readings for key, url in reading.sources.items()},
                "failed": [entry for reading in readings for entry in reading.failed],
                "notes": [*blind, *(note for reading in readings for note in reading.notes)],
            },
            Health,
        )
