"""assess.intake: a technology — a repository URL, a registry URL or a bare name — resolved to what can be fetched.

A GitHub URL is the repository; its package is the one its manifest declares (`pyproject.toml`, `Cargo.toml`,
`package.json`, in that order), read through the contents API, no clone — and only if the registry's entry for that
name points back at the same repository: a name taken on the registry by someone else is a note, never the package.
A registry URL is that entry and its source repository; a bare name is tried on PyPI, npm and crates.io, in that
order, the first entry that exists winning. Nothing resolvable is an AssessError naming every URL tried."""

import base64
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote

import eserde
import msgspec

from e_taxis.workflow.models.assess import Candidate, Fetched, Registry
from e_taxis.workflow.models.error import AssessError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from e_taxis.workflow.models.ports import ApiPort

##### DEFAULTS #####
GITHUB: Final[re.Pattern[str]] = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?]|$)", re.IGNORECASE)
REPO: str = "https://api.github.com/repos/{repo}"
CONTENTS: str = REPO + "/contents/{path}"
ENTRIES: Final[Mapping[Registry, str]] = MappingProxyType(
    {
        Registry.PYPI: "https://pypi.org/pypi/{name}/json",
        Registry.NPM: "https://registry.npmjs.org/{name}",
        Registry.CRATES: "https://crates.io/api/v1/crates/{name}",
    }
)
### a registry's own page for a package: the URL a human pastes.
PAGES: Final[Mapping[Registry, re.Pattern[str]]] = MappingProxyType(
    {
        Registry.PYPI: re.compile(r"^(?:https?://)?pypi\.org/project/([^/?#]+)", re.IGNORECASE),
        Registry.NPM: re.compile(r"^(?:https?://)?(?:www\.)?npmjs\.com/package/((?:@[^/]+/)?[^/?#]+)", re.IGNORECASE),
        Registry.CRATES: re.compile(r"^(?:https?://)?crates\.io/crates/([^/?#]+)", re.IGNORECASE),
    }
)
MANIFESTS: Final[Mapping[str, Registry]] = MappingProxyType(
    {"pyproject.toml": Registry.PYPI, "Cargo.toml": Registry.CRATES, "package.json": Registry.NPM}
)


##### UTILITIES #####
def name_pyproject(text: str) -> str:
    match eserde.loads(text, format=eserde.Format.TOML):
        case {"project": {"name": str() as name}} | {"tool": {"poetry": {"name": str() as name}}}:
            return name
        case _:
            return ""


def name_cargo(text: str) -> str:
    match eserde.loads(text, format=eserde.Format.TOML):
        case {"package": {"name": str() as name}}:
            return name
        case _:
            return ""


def name_package(text: str) -> str:
    match msgspec.json.decode(text):
        case {"name": str() as name}:
            return name
        case _:
            return ""


def links_pypi(entry: Any) -> list[str]:
    match entry:
        case {"info": {"project_urls": dict() as urls, **rest}}:
            return [*map(str, urls.values()), str(rest.get("home_page") or "")]
        case {"info": {"home_page": str() as home}}:
            return [home]
        case _:
            return []


def links_npm(entry: Any) -> list[str]:
    match entry:
        case {"repository": {"url": str() as url}} | {"repository": str() as url}:
            return [url, str(entry.get("homepage") or "")]
        case {"homepage": str() as home}:
            return [home]
        case _:
            return []


def links_crates(entry: Any) -> list[str]:
    match entry:
        case {"crate": {"repository": str() as url, **rest}}:
            return [url, str(rest.get("homepage") or "")]
        case _:
            return []


NAMES: Final[Mapping[str, Callable[[str], str]]] = MappingProxyType(
    {"pyproject.toml": name_pyproject, "Cargo.toml": name_cargo, "package.json": name_package}
)
LINKS: Final[Mapping[Registry, Callable[[Any], list[str]]]] = MappingProxyType(
    {Registry.PYPI: links_pypi, Registry.NPM: links_npm, Registry.CRATES: links_crates}
)


##### TYPES #####
class AssessIntake:
    """The technology resolved over public APIs (ApiPort); `topics` are the soa.yaml topics a `--topic` may name."""

    __slots__ = ("_api", "_topics")

    def __init__(self, api: ApiPort, topics: Iterable[str]) -> None:
        self._api = api
        self._topics = frozenset(topics)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_repo(links: Iterable[str]) -> str:
        """The first GitHub repository among `links`, as `owner/repo`."""
        found = (GITHUB.search(link) for link in links)
        return next((f"{hit.group(1)}/{hit.group(2)}" for hit in found if hit), "")

    async def _common_entry(self, registry: Registry, name: str) -> tuple[Fetched, str]:
        """A registry's entry for `name`, and the repository it points at (empty when none)."""
        fetched = await self._api.get(ENTRIES[registry].format(name=quote(name, safe="@")))
        entry = msgspec.json.decode(fetched.body) if fetched.ok else {}
        return fetched, self._common_repo(LINKS[registry](entry))

    async def _resolve_manifest(self, repo: str, file: str) -> tuple[Registry, str] | None:
        fetched = await self._api.get(CONTENTS.format(repo=repo, path=file))
        match msgspec.json.decode(fetched.body) if fetched.ok else {}:
            case {"content": str() as content, "encoding": "base64"}:
                name = NAMES[file](base64.b64decode(content).decode())
                return (MANIFESTS[file], name) if name else None
            case _:
                return None

    async def _resolve_verified(self, repo: str, registry: Registry, name: str) -> str:
        """Empty when `registry`'s `name` points back at `repo`; the note saying where it points otherwise."""
        fetched, source = await self._common_entry(registry, name)
        match (fetched.ok, source.lower() == repo.lower()):
            case (True, True):
                return ""
            case (False, _):
                return f"{registry} has no {name!r} ({fetched.url}: {fetched.status or fetched.error}): no registry"
            case _:
                return f"{registry} {name!r} points at {source or 'no repository'}, not {repo}: no registry"

    async def _common_canonical(self, repo: str) -> tuple[Fetched, str]:
        """The repository's current `owner/name` (GitHub answers a renamed one under its new name); empty: no answer."""
        fetched = await self._api.get(REPO.format(repo=repo))
        match msgspec.json.decode(fetched.body) if fetched.ok else None:
            case {"full_name": str() as full}:
                return fetched, full
            case _:
                return fetched, ""

    async def _resolve_github(self, tech: str, owner: str, name: str) -> Candidate:
        fetched, repo = await self._common_canonical(f"{owner}/{name}")
        root = await self._api.get(CONTENTS.format(repo=repo, path="")) if repo else fetched
        match msgspec.json.decode(root.body) if root.ok and repo else None:
            case list() as listing:
                present = {str(item.get("name", "")) for item in listing}
            case _:
                msg = f"{tech}: nothing resolvable — tried {root.url} ({root.status or root.error})"
                raise AssessError(msg)
        declared = [
            found for file in MANIFESTS if file in present if (found := await self._resolve_manifest(repo, file))
        ]
        notes = [await self._resolve_verified(repo, registry, package) for registry, package in declared]
        chosen = next((pair for pair, note in zip(declared, notes, strict=True) if not note), None)
        return Candidate(
            tech=tech,
            name=chosen[1] if chosen else name,
            repo=repo,
            package=chosen[1] if chosen else "",
            registry=chosen[0] if chosen else None,
            notes=tuple(note for note in notes if note),
        )

    async def _resolve_registry(self, tech: str, registries: tuple[Registry, ...], name: str) -> Candidate:
        tried = [(registry, *(await self._common_entry(registry, name))) for registry in registries]
        match next(((registry, source) for registry, fetched, source in tried if fetched.ok), None):
            case (registry, source):
                _, repo = await self._common_canonical(source) if source else (None, "")
                kept = repo or source
                notes = (
                    (f"GitHub did not answer for {source}: its name is the registry's",) if source and not repo else ()
                )
                return Candidate(tech=tech, name=name, repo=kept, package=name, registry=registry, notes=notes)
            case _:
                said = ", ".join(f"{fetched.url} ({fetched.status or fetched.error})" for _, fetched, _ in tried)
                msg = f"{tech}: nothing resolvable — tried {said}"
                raise AssessError(msg)

    def _resolve_topic(self, topic: str) -> str:
        match topic in self._topics or not topic:
            case True:
                return topic
            case _:
                msg = f"topic {topic!r} is not in soa.yaml: {', '.join(sorted(self._topics)) or 'none declared'}"
                raise AssessError(msg)

    ############################################################

    ##### PUBLIC #####

    async def resolve(self, tech: str, topic: str = "") -> Candidate:
        """The candidate `tech` names, on `topic` (empty: none given)."""
        kept, text = self._resolve_topic(topic), tech.strip()
        page = next(((registry, hit.group(1)) for registry, rx in PAGES.items() if (hit := rx.search(text))), None)
        match (GITHUB.search(text), page):
            case (re.Match() as hit, _):
                found = await self._resolve_github(text, hit.group(1), hit.group(2))
            case (None, (registry, name)):
                found = await self._resolve_registry(text, (registry,), name)
            case _:
                found = await self._resolve_registry(text, tuple(Registry), text)
        return msgspec.structs.replace(found, topic=kept)
