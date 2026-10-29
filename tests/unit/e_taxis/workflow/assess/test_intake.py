"""tests/unit/e_taxis/workflow/assess/intake: a URL or a name resolved to its repository and package — over recorded
answers. rtk's Cargo name is taken on crates.io by another repository: a note, never the package. jcrist/msgspec was
renamed msgspec/msgspec: the canonical name is the one kept."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.assess.intake import AssessIntake
from e_taxis.workflow.models.assess import Candidate, Registry
from e_taxis.workflow.models.error import AssessError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.ports import ApiPort

TOPICS = ("memory", "token-economy")
GH = "https://api.github.com/repos"


@pytest.mark.parametrize(
    ("tech", "expected"),
    [
        (
            "https://github.com/rtk-ai/rtk",
            Candidate(
                tech="https://github.com/rtk-ai/rtk",
                name="rtk",
                repo="rtk-ai/rtk",
                topic="token-economy",
                notes=("crates 'rtk' points at reachingforthejack/rtk, not rtk-ai/rtk: no registry",),
            ),
        ),
        (
            "https://github.com/jcrist/msgspec.git",
            Candidate(
                tech="https://github.com/jcrist/msgspec.git",
                name="msgspec",
                repo="msgspec/msgspec",
                package="msgspec",
                registry=Registry.PYPI,
                topic="token-economy",
            ),
        ),
        (
            "https://pypi.org/project/msgspec/",
            Candidate(
                tech="https://pypi.org/project/msgspec/",
                name="msgspec",
                repo="msgspec/msgspec",
                package="msgspec",
                registry=Registry.PYPI,
                topic="token-economy",
            ),
        ),
        (
            "https://www.npmjs.com/package/express",
            Candidate(
                tech="https://www.npmjs.com/package/express",
                name="express",
                repo="expressjs/express",
                package="express",
                registry=Registry.NPM,
                topic="token-economy",
                notes=("GitHub did not answer for expressjs/express: its name is the registry's",),
            ),
        ),
        (
            "express",
            Candidate(
                tech="express",
                name="express",
                repo="expressjs/express",
                package="express",
                registry=Registry.NPM,
                topic="token-economy",
                notes=("GitHub did not answer for expressjs/express: its name is the registry's",),
            ),
        ),
    ],
    ids=["github-foreign-crate", "github-renamed-pypi", "pypi-page", "npm-page", "bare-name"],
)
async def test_intake_resolve(api: ApiPort, tech: str, expected: Candidate) -> None:
    assert await AssessIntake(api, TOPICS).resolve(tech, "token-economy") == expected


@pytest.mark.parametrize(
    ("tech", "topic", "match"),
    [
        (
            "https://github.com/nobody/nothing",
            "",
            r"nothing resolvable — tried https://api.github.com/repos/nobody/nothing \(404\)",
        ),
        (
            "no-such-thing",
            "",
            r"tried https://pypi.org/pypi/no-such-thing/json \(404\), https://registry.npmjs.org/no-such",
        ),
        ("https://crates.io/crates/absent", "", r"tried https://crates.io/api/v1/crates/absent \(404\)$"),
        ("msgspec", "cooking", r"topic 'cooking' is not in soa.yaml: memory, token-economy"),
    ],
    ids=["github", "bare", "crates-page", "topic"],
)
async def test_intake_resolve_refuses(api: ApiPort, tech: str, topic: str, match: str) -> None:
    with pytest.raises(AssessError, match=match):
        await AssessIntake(api, TOPICS).resolve(tech, topic)


async def test_intake_resolve_refuses_with_no_topic_declared(api: ApiPort) -> None:
    with pytest.raises(AssessError, match="none declared"):
        await AssessIntake(api, ()).resolve("msgspec", "memory")


async def test_intake_resolve_github_listing_unreadable(stub: Callable[[Mapping[str, Any]], ApiPort]) -> None:
    api = stub({f"{GH}/o/r": {"full_name": "o/r"}, f"{GH}/o/r/contents/": {"message": "a file, not a folder"}})
    with pytest.raises(AssessError, match=r"tried https://api.github.com/repos/o/r/contents/ \(200\)"):
        await AssessIntake(api, ()).resolve("https://github.com/o/r")


@pytest.mark.parametrize(
    ("files", "answers", "expected"),
    [
        (
            {
                "pyproject.toml": '[tool.poetry]\nname = "poet"\n',
                "Cargo.toml": "[workspace]\n",
                "package.json": '{"name": "@o/r"}',
            },
            {
                "https://pypi.org/pypi/poet/json": {"info": {"home_page": "https://github.com/o/r"}},
                "https://registry.npmjs.org/@o%2Fr": {"homepage": "https://github.com/someone/else"},
            },
            Candidate(
                tech="https://github.com/o/r",
                name="poet",
                repo="o/r",
                package="poet",
                registry=Registry.PYPI,
                notes=("npm '@o/r' points at someone/else, not o/r: no registry",),
            ),
        ),
        (
            {"pyproject.toml": "[build-system]\n", "package.json": "[]"},
            {},
            Candidate(tech="https://github.com/o/r", name="r", repo="o/r"),
        ),
        (
            {"package.json": ""},
            {f"{GH}/o/r/contents/package.json": {"encoding": "none"}},
            Candidate(tech="https://github.com/o/r", name="r", repo="o/r"),
        ),
        (
            {"Cargo.toml": '[package]\nname = "gone"\n'},
            {},
            Candidate(
                tech="https://github.com/o/r",
                name="r",
                repo="o/r",
                notes=("crates has no 'gone' (https://crates.io/api/v1/crates/gone: 404): no registry",),
            ),
        ),
    ],
    ids=["poetry-wins-npm-foreign", "no-name-declared", "not-base64", "crate-unpublished"],
)
async def test_intake_resolve_manifests(
    stub: Callable[[Mapping[str, Any]], ApiPort],
    encoded: Callable[[str], dict[str, str]],
    files: dict[str, str],
    answers: dict[str, Any],
    expected: Candidate,
) -> None:
    listing = {f"{GH}/o/r/contents/": [{"name": name} for name in files]}
    contents = {f"{GH}/o/r/contents/{name}": encoded(text) for name, text in files.items()}
    api = stub({f"{GH}/o/r": {"full_name": "o/r"}, **listing, **contents, **answers})
    assert await AssessIntake(api, ()).resolve("https://github.com/o/r") == expected


@pytest.mark.parametrize(
    ("answers", "repo"),
    [
        ({"https://pypi.org/pypi/p/json": {"info": {"project_urls": {"Source": "https://github.com/a/b"}}}}, "a/b"),
        ({"https://pypi.org/pypi/p/json": {"info": {}}}, ""),
        ({"https://registry.npmjs.org/p": {"repository": "git+https://github.com/c/d.git"}}, "c/d"),
        ({"https://registry.npmjs.org/p": {"name": "p"}}, ""),
        ({"https://crates.io/api/v1/crates/p": {"crate": {"repository": "https://github.com/e/f"}}}, "e/f"),
        ({"https://crates.io/api/v1/crates/p": {"crate": {}}}, ""),
    ],
    ids=["pypi-urls", "pypi-none", "npm-string", "npm-none", "crates", "crates-none"],
)
async def test_intake_resolve_registry_links(
    stub: Callable[[Mapping[str, Any]], ApiPort], answers: dict[str, Any], repo: str
) -> None:
    canonical = {f"{GH}/{repo}": {"full_name": repo}} if repo else {}
    found = await AssessIntake(stub({**answers, **canonical}), ()).resolve("p")
    assert (found.repo, found.notes) == (repo, ())


SEARCHED = "https://api.github.com/search/repositories?q={q}+in:name&sort=stars&order=desc&per_page=10"


@pytest.mark.parametrize(
    ("tech", "hits", "repo", "how"),
    [
        ("auto ontology", ["big/onto", "nv/auto-ontology"], "nv/auto-ontology", "its exact name of 2"),
        ("auto ontology", ["big/onto", "nv/other"], "big/onto", "the most starred hit of 2"),
        ("nowhere", ["big/nowhere"], "big/nowhere", "its exact name of 1"),
    ],
    ids=["exact", "starred", "no-registry"],
)
async def test_intake_resolve_searches_a_name_on_github(
    stub: Callable[[Mapping[str, Any]], ApiPort], tech: str, hits: list[str], repo: str, how: str
) -> None:
    query = tech.replace(" ", "-")
    answers = {
        SEARCHED.format(q=query): {"items": [{"full_name": hit, "name": hit.split("/")[1]} for hit in hits]},
        f"{GH}/{repo}": {"full_name": repo},
        f"{GH}/{repo}/contents/": [],
    }
    found = await AssessIntake(stub(answers), ()).resolve(tech)
    assert (found.repo, found.notes[0]) == (repo, f"resolved by GitHub search to {repo} ({how})")


async def test_intake_resolve_search_without_a_hit_is_refused(stub: Callable[[Mapping[str, Any]], ApiPort]) -> None:
    api = stub({SEARCHED.format(q="no-such-thing"): {"items": []}})
    with pytest.raises(AssessError, match="no such thing: nothing resolvable"):
        await AssessIntake(api, ()).resolve("no such thing")
