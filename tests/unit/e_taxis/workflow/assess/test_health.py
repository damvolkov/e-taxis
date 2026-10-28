"""tests/unit/e_taxis/workflow/assess/health: dated KPIs over recorded answers, and every source that fails named.

rtk publishes no package (its crates.io name belongs to another repository), so its cadence comes from GitHub's
releases: 441 of them across five pages, 351 pre-releases, 90 stable within the year. msgspec is on PyPI: deps.dev's
versions and dependents, pypistats' month. Neither repository has a Scorecard on deps.dev — a named failure."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.assess.health import AssessHealth
from e_taxis.workflow.models.assess import Candidate, Health, Registry

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.ports import ApiPort

GH = "https://api.github.com/repos/o/r"
SEARCH = "https://api.github.com/search/issues?q=repo:o/r+type:issue"
DEPS = "https://api.deps.dev"
PROJECT = f"{DEPS}/v3/projects/github.com%2Fo%2Fr"
RELEASES = f"{GH}/releases?per_page=100&page="


async def test_health_measure_a_repository_without_registry(api: ApiPort, rtk: Candidate, now: dt.datetime) -> None:
    found = await AssessHealth(api).measure(rtk, now)
    assert found == Health(
        measured_at="2026-10-28T15:00:00+00:00",
        last_release="2026-10-25T18:00:11+00:00",
        releases_per_year=90.0,
        license="Apache-2.0",
        open_issue_ratio=0.4758,
        contributors=192,
        sources={
            "license": "https://api.github.com/repos/rtk-ai/rtk",
            "contributors": "https://api.github.com/repos/rtk-ai/rtk/contributors?per_page=1&anon=true",
            "open_issue_ratio": "https://api.github.com/search/issues?q=repo:rtk-ai/rtk+type:issue&per_page=1",
            "last_release": "https://api.github.com/repos/rtk-ai/rtk/releases",
            "releases_per_year": "https://api.github.com/repos/rtk-ai/rtk/releases",
        },
        failed=(
            "scorecard: https://api.deps.dev/v3/projects/github.com%2Frtk-ai%2Frtk → deps.dev holds no Scorecard for rtk-ai/rtk",
        ),
        notes=("no registry: downloads and dependents unmeasured", "351 pre-releases and drafts not counted"),
    )


async def test_health_measure_a_pypi_package(api: ApiPort, msgspec_candidate: Candidate, now: dt.datetime) -> None:
    found = await AssessHealth(api).measure(msgspec_candidate, now)
    assert (found.last_release, found.releases_per_year, found.downloads_month, found.dependents) == (
        "2026-09-29T14:13:12+00:00",
        4.0,
        29813196,
        6546,
    )
    assert (found.license, found.contributors, found.open_issue_ratio, found.notes) == ("BSD-3-Clause", 83, 0.3476, ())
    assert found.sources["dependents"].endswith("/pypi/packages/msgspec/versions/0.22.0:dependents")


async def test_health_measure_names_every_dead_source(api: ApiPort, now: dt.datetime) -> None:
    ghost = Candidate(tech="x", name="ghost", repo="ghost/none", package="ghost", registry=Registry.NPM)
    found = await AssessHealth(api).measure(ghost, now)
    assert (found.license, found.contributors, found.open_issue_ratio, found.downloads_month) == (None,) * 4
    assert [entry.partition(":")[0] for entry in found.failed] == [
        "license",
        "contributors",
        "open_issue_ratio",
        "open_issue_ratio",
        "scorecard",
        "last_release",
        "releases_per_year",
        "dependents",
        "downloads_month",
    ]
    assert found.failed[0] == "license: https://api.github.com/repos/ghost/none → 404"


async def test_health_measure_a_renamed_repository_cannot_be_searched(api: ApiPort, now: dt.datetime) -> None:
    found = await AssessHealth(api).measure(Candidate(tech="x", name="msgspec", repo="jcrist/msgspec"), now)
    assert found.license == "BSD-3-Clause"
    assert (
        "https://api.github.com/search/issues?q=repo:jcrist/msgspec+type:issue+state:open&per_page=1 → 422"
        in "\n".join(found.failed)
    )


async def test_health_measure_nothing_to_read(api: ApiPort, now: dt.datetime) -> None:
    found = await AssessHealth(api).measure(Candidate(tech="x", name="x"), now)
    assert (found.failed, found.sources, found.notes) == (
        (),
        {},
        (
            "no repository: licence, contributors, issues and Scorecard unmeasured",
            "no registry: downloads and dependents unmeasured",
        ),
    )


async def test_health_measure_a_transport_failure(
    api: ApiPort, outage: dict[str, str], rtk: Candidate, now: dt.datetime
) -> None:
    outage["https://api.github.com/repos/rtk-ai/rtk"] = "ConnectionError: refused"
    found = await AssessHealth(api).measure(rtk, now)
    assert found.license is None
    assert found.failed[0] == "license: https://api.github.com/repos/rtk-ai/rtk → ConnectionError: refused"


@pytest.mark.parametrize(
    ("answers", "expected", "failed"),
    [
        (
            {GH: {"license": None}, f"{GH}/contributors?per_page=1&anon=true": [{"login": "a"}, {"login": "b"}]},
            {"license": None, "contributors": 2},
            ("license: https://api.github.com/repos/o/r → no licence declared",),
        ),
        (
            {f"{GH}/contributors?per_page=1&anon=true": {"message": "too large"}},
            {"contributors": None},
            ("contributors: https://api.github.com/repos/o/r/contributors?per_page=1&anon=true → unexpected shape",),
        ),
        (
            {f"{SEARCH}+state:open&per_page=1": {"total_count": 0}, f"{SEARCH}&per_page=1": {"total_count": 0}},
            {"open_issue_ratio": None},
            (
                "open_issue_ratio: https://api.github.com/search/issues?q=repo:o/r+type:issue&per_page=1 → no issue ever opened",
            ),
        ),
        (
            {PROJECT: {"scorecard": {"overallScore": 7, "date": "2026-10-20T00:00:00Z"}}},
            {"scorecard": 7.0},
            (),
        ),
        (
            {f"{RELEASES}1": []},
            {"last_release": None},
            (
                "last_release: https://api.github.com/repos/o/r/releases → no stable release published",
                "releases_per_year: https://api.github.com/repos/o/r/releases → no stable release published",
            ),
        ),
        (
            {f"{RELEASES}1": {"message": "moved"}},
            {"last_release": None},
            ("last_release: unexpected shape", "releases_per_year: unexpected shape"),
        ),
    ],
    ids=["no-licence-unpaged", "contributors-shape", "no-issue", "scorecard", "no-release", "releases-shape"],
)
async def test_health_measure_repository_shapes(
    stub: Callable[[Mapping[str, Any]], ApiPort],
    now: dt.datetime,
    answers: dict[str, Any],
    expected: dict[str, Any],
    failed: tuple[str, ...],
) -> None:
    found = await AssessHealth(stub(answers)).measure(Candidate(tech="x", name="r", repo="o/r"), now)
    assert {key: getattr(found, key) for key in expected} == expected
    assert set(failed) <= set(found.failed)


@pytest.mark.parametrize(
    ("pages", "every", "rate", "note"),
    [
        ((100, 100, 100, 100, 100), 0.73, 501.0, "cadence extrapolated over the 364 days the listing reached"),
        ((100, 30), 3.0, 122.0, ""),
    ],
    ids=["capped-short-of-a-year", "whole-year"],
)
async def test_health_measure_releases_across_pages(
    stub: Callable[[Mapping[str, Any]], ApiPort],
    releases: Callable[..., list[dict[str, Any]]],
    now: dt.datetime,
    pages: tuple[int, ...],
    every: float,
    rate: float,
    note: str,
) -> None:
    starts = [sum(pages[:at]) for at in range(len(pages))]
    answers = {
        f"{RELEASES}{at + 1}": releases(size, every, start=start)
        for at, (size, start) in enumerate(zip(pages, starts, strict=True))
    }
    found = await AssessHealth(stub(answers)).measure(Candidate(tech="x", name="r", repo="o/r"), now)
    assert found.releases_per_year == pytest.approx(rate, rel=0.01)
    assert (note in found.notes) if note else not any(n.startswith("cadence") for n in found.notes)


async def test_health_measure_a_release_page_that_fails(
    stub: Callable[[Mapping[str, Any]], ApiPort], releases: Callable[..., list[dict[str, Any]]], now: dt.datetime
) -> None:
    api = stub({f"{RELEASES}1": releases(100, 1.0), f"{RELEASES}2": (502, {"message": "bad gateway"})})
    found = await AssessHealth(api).measure(Candidate(tech="x", name="r", repo="o/r"), now)
    assert found.failed[-1] == "releases_per_year: https://api.github.com/repos/o/r/releases?per_page=100&page=2 → 502"


@pytest.mark.parametrize(
    ("registry", "answers", "expected"),
    [
        (
            Registry.CRATES,
            {
                f"{DEPS}/v3/systems/cargo/packages/c": {
                    "versions": [
                        {"versionKey": {"version": "1.0.0"}, "publishedAt": "2026-10-01T00:00:00Z", "isDefault": True},
                        {"versionKey": {"version": "0.1.0"}, "publishedAt": "2024-01-01T00:00:00Z"},
                    ]
                },
                "https://crates.io/api/v1/crates/c/reverse_dependencies?per_page=1": {"meta": {"total": 12}},
                "https://crates.io/api/v1/crates/c/downloads": {
                    "version_downloads": [
                        {"date": "2026-10-27", "downloads": 5},
                        {"date": "2026-09-01", "downloads": 99},
                    ],
                    "meta": {"extra_downloads": [{"date": "2026-10-20", "downloads": 2}]},
                },
            },
            {"releases_per_year": 1.0, "dependents": 12, "downloads_month": 7},
        ),
        (
            Registry.NPM,
            {
                f"{DEPS}/v3/systems/npm/packages/c": {
                    "versions": [
                        {"versionKey": {"version": "2.0.0"}, "publishedAt": "2026-10-01T00:00:00Z", "isDefault": True}
                    ]
                },
                f"{DEPS}/v3alpha/systems/npm/packages/c/versions/2.0.0:dependents": {"count": "many"},
                "https://api.npmjs.org/downloads/point/last-month/c": {"downloads": 40},
            },
            {"dependents": None, "downloads_month": 40},
        ),
        (
            Registry.PYPI,
            {
                f"{DEPS}/v3/systems/pypi/packages/c": {"versions": [{"versionKey": {"version": "1"}}]},
                "https://pypistats.org/api/packages/c/recent": {"data": {}},
            },
            {"last_release": None, "dependents": None, "downloads_month": None},
        ),
        (
            Registry.CRATES,
            {"https://crates.io/api/v1/crates/c/downloads": {"version_downloads": []}},
            {"downloads_month": None, "last_release": None},
        ),
        (
            Registry.NPM,
            {
                f"{DEPS}/v3/systems/npm/packages/c": {
                    "versions": [
                        {"versionKey": {"version": "3"}, "publishedAt": "2026-10-01T00:00:00Z", "isDefault": True}
                    ]
                },
                "https://api.npmjs.org/downloads/point/last-month/c": {"error": "not found"},
            },
            {"downloads_month": None, "dependents": None, "releases_per_year": 1.0},
        ),
    ],
    ids=["crates", "npm-dependents-shape", "pypi-shapes", "crates-shape", "npm-shape"],
)
async def test_health_measure_registry_shapes(
    stub: Callable[[Mapping[str, Any]], ApiPort],
    now: dt.datetime,
    registry: Registry,
    answers: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    candidate = Candidate(tech="c", name="c", package="c", registry=registry)
    found = await AssessHealth(stub(answers)).measure(candidate, now)
    assert {key: getattr(found, key) for key in expected} == expected
