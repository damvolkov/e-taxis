"""compare.intake: what a repository declares — every dependency, its version, its manifest, where it is imported.

**Manifests.** At the repository's root: `pyproject.toml` (`[project]` dependencies, its optional-dependencies and
the PEP 735 `[dependency-groups]`; `uv.lock` resolves the version), `Cargo.toml` (dependencies, dev-, build- and
workspace dependencies; `Cargo.lock`), `package.json` (dependencies, dev-, peer- and optional; `package-lock.json`).
Compose files (`compose.y*ml`, `docker-compose.y*ml`) are found anywhere under it: every service's image, its tag
the version. The walk never enters `.venv`, `node_modules` or `.git`.

**Imports.** One pass over the walked source files (Python, Rust, JS/TS) extracts the top-level modules each imports;
a dependency is looked up by the modules it provides: a Python distribution's own `top_level.txt` or `RECORD` in the
repository's `.venv` when one is there (`e-serde` provides `eserde`), its normalized name otherwise; a crate's name
with `_` for `-`; an npm package's name. The first IMPORTS files are kept, sorted; `imported` counts them all.

No directory, or one that declares nothing, is a CompareError; a topic radar.yaml does not hold is one too. The walk
and the reads are sync and run in a worker thread, off the loop."""

import itertools
import re
from dataclasses import dataclass
from functools import reduce
from operator import itemgetter
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.compare import Dependency, Ecosystem, Stack
from e_taxis.workflow.models.error import CompareError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

##### DEFAULTS #####
IMPORTS: int = 10
SKIP: Final[frozenset[str]] = frozenset({".venv", "node_modules", ".git"})
COMPOSE: Final[re.Pattern[str]] = re.compile(r"^(?:docker-)?compose\.ya?ml$")
REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\]]*\])?")
SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[-_.]+")
PYTHON: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]*(?:from[ \t]+([A-Za-z_]\w*)[\w.]*[ \t]+import\b|import[ \t]+([^\n#;]+))", re.MULTILINE
)
### a path segment before `::` catches `use x::…`, `x::f()` and `#[derive(x::T)]` alike; only declared crates are read.
RUST: Final[re.Pattern[str]] = re.compile(r"\bextern[ \t]+crate[ \t]+([A-Za-z_]\w*)|\b([A-Za-z_]\w*)::")
JS: Final[re.Pattern[str]] = re.compile(
    r"""(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+)['"]((?:@[\w.-]+/)?[\w.-]+)"""
)
SOURCES: Final[Mapping[str, Ecosystem]] = MappingProxyType(
    {
        ".py": Ecosystem.PYTHON,
        ".pyi": Ecosystem.PYTHON,
        ".rs": Ecosystem.RUST,
        **dict.fromkeys((".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts"), Ecosystem.JS),
    }
)
CARGO: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("dependencies",), ""),
    (("dev-dependencies",), "dev"),
    (("build-dependencies",), "build"),
    (("workspace", "dependencies"), "workspace"),
)
NPM: Final[tuple[tuple[str, str], ...]] = (
    ("dependencies", ""),
    ("devDependencies", "dev"),
    ("peerDependencies", "peer"),
    ("optionalDependencies", "optional"),
)
SITE: str = ".venv/lib/*/site-packages/*.dist-info"
NOT_MODULES: Final[tuple[str, ...]] = (".dist-info", ".data", ".pth")

type Declared = tuple[str, str, str]


##### UTILITIES #####
def table_at(data: Any, path: Iterable[str]) -> dict[str, Any]:
    """The table at `path` inside parsed TOML/JSON, empty when any step of it is missing."""
    return reduce(lambda at, key: at.get(key) or {}, path, data or {})


def key_python(name: str) -> str:
    """PEP 503: case-folded, every run of `-_.` one `-`."""
    return SEPARATORS.sub("-", name).lower()


def key_rust(name: str) -> str:
    return name.replace("_", "-").lower()


def key_js(name: str) -> str:
    return name


def declared_pyproject(data: Any) -> list[Declared]:
    """(name, scope, specifier) for the project's dependencies, its extras and its dependency groups."""
    project = table_at(data, ("project",))
    specs = [
        *(("", spec) for spec in project.get("dependencies") or ()),
        *(
            (f"optional:{extra}", spec)
            for extra, listed in table_at(project, ("optional-dependencies",)).items()
            for spec in listed
        ),
        ### an `{include-group = …}` entry names a group already read on its own.
        *(
            (f"group:{group}", spec)
            for group, listed in table_at(data, ("dependency-groups",)).items()
            for spec in listed
            if type(spec) is str
        ),
    ]
    return [
        (hit.group(1), scope, spec[hit.end() :].split(";", 1)[0].strip())
        for scope, spec in specs
        if (hit := REQUIREMENT.match(spec))
    ]


def version_cargo(spec: Any) -> str:
    match spec:
        case str() as version:
            return version
        case {"version": str() as version}:
            return version
        case {"workspace": True}:
            return "workspace"
        case {"path": str() as path}:
            return f"path {path}"
        case {"git": str() as git}:
            return f"git {git}"
        case _:
            return ""


def declared_cargo(data: Any) -> list[Declared]:
    return [(name, scope, version_cargo(spec)) for path, scope in CARGO for name, spec in table_at(data, path).items()]


def declared_npm(data: Any) -> list[Declared]:
    return [(name, scope, str(spec)) for field, scope in NPM for name, spec in table_at(data, (field,)).items()]


def locked_packages(data: Any, key: Callable[[str], str]) -> dict[str, str]:
    """`[[package]]` name → version (uv.lock, Cargo.lock); a name locked at several versions lists them all."""
    pairs = sorted(
        {(key(str(row["name"])), str(row["version"])) for row in data.get("package") or () if "version" in row}
    )
    return {name: ", ".join(map(itemgetter(1), rows)) for name, rows in itertools.groupby(pairs, key=itemgetter(0))}


def locked_uv(data: Any) -> dict[str, str]:
    return locked_packages(data, key_python)


def locked_cargo(data: Any) -> dict[str, str]:
    return locked_packages(data, key_rust)


def locked_npm(data: Any) -> dict[str, str]:
    """package-lock.json v2/v3 (`packages`, the root's own `node_modules/<name>` entries), v1 (`dependencies`)."""
    nested = {
        path.removeprefix("node_modules/"): str(entry.get("version", ""))
        for path, entry in table_at(data, ("packages",)).items()
        if path.startswith("node_modules/") and "/node_modules/" not in path
    }
    flat = {name: str(entry.get("version", "")) for name, entry in table_at(data, ("dependencies",)).items()}
    return nested or flat


def image_parts(image: str) -> tuple[str, str]:
    """(name, version) of an image reference: the tag after the last `:` past the last `/`, then any digest."""
    ref, _, digest = image.partition("@")
    head, sep, tag = ref.rpartition(":")
    name, version = (head, tag) if sep and "/" not in tag else (ref, "")
    return name, "@".join(part for part in (version, digest) if part)


def modules_python(text: str) -> set[str]:
    """The top-level modules a Python file imports (absolute imports only)."""
    found = PYTHON.findall(text)
    listed = (part.strip().split(maxsplit=1)[0] for _, names in found for part in names.split(",") if part.strip())
    return {*(first for first, _ in found if first), *(name.split(".", 1)[0] for name in listed)}


def modules_rust(text: str) -> set[str]:
    return {crate or segment for crate, segment in RUST.findall(text)}


def modules_js(text: str) -> set[str]:
    return set(JS.findall(text))


def modules_record(dist: Path) -> tuple[str, ...]:
    """The top-level modules a distribution installs: its `top_level.txt`, else the first segments of its RECORD."""
    top, record = dist / "top_level.txt", dist / "RECORD"
    match (top.is_file(), record.is_file()):
        case (True, _):
            lines = top.read_text().split()
        case (_, True):
            lines = [row.split(",", 1)[0].split("/", 1)[0] for row in record.read_text().splitlines() if row]
        case _:
            lines = []
    names = {line.partition(".")[0] for line in lines if not line.endswith(NOT_MODULES)}
    return tuple(sorted(name for name in names if name.isidentifier() and name != "__pycache__"))


##### TYPES #####
@dataclass(frozen=True, slots=True)
class Manifest:
    """One root manifest: its world, how its dependencies and its lockfile are read."""

    ecosystem: Ecosystem
    declared: Callable[[Any], list[Declared]]
    lock: str
    locked: Callable[[Any], dict[str, str]]
    key: Callable[[str], str]


MANIFESTS: Final[Mapping[str, Manifest]] = MappingProxyType(
    {
        "pyproject.toml": Manifest(Ecosystem.PYTHON, declared_pyproject, "uv.lock", locked_uv, key_python),
        "Cargo.toml": Manifest(Ecosystem.RUST, declared_cargo, "Cargo.lock", locked_cargo, key_rust),
        "package.json": Manifest(Ecosystem.JS, declared_npm, "package-lock.json", locked_npm, key_js),
    }
)
FORMATS: Final[Mapping[str, eserde.Format]] = MappingProxyType(
    {".toml": eserde.Format.TOML, ".lock": eserde.Format.TOML, ".json": eserde.Format.JSON}
)
MODULES: Final[Mapping[Ecosystem, Callable[[str], set[str]]]] = MappingProxyType(
    {Ecosystem.PYTHON: modules_python, Ecosystem.RUST: modules_rust, Ecosystem.JS: modules_js}
)


class CompareIntake:
    """Reads one repository from disk; `topics` are the radar.yaml topics a `--topic` may name."""

    __slots__ = ("_topics",)

    def __init__(self, topics: Iterable[str]) -> None:
        self._topics = frozenset(topics)

    ##### PRIVATE METHODS #####

    @classmethod
    def _read_files(cls, folder: Path) -> Iterator[Path]:
        """Every file under `folder`, sorted, never inside SKIP or through a symlinked folder."""
        entries = sorted(folder.iterdir())
        yield from (entry for entry in entries if entry.is_file())
        yield from itertools.chain.from_iterable(
            cls._read_files(entry)
            for entry in entries
            if entry.is_dir() and not entry.is_symlink() and entry.name not in SKIP
        )

    @staticmethod
    def _read_parsed(path: Path) -> Any:
        return eserde.loads(path.read_text(), format=FORMATS[path.suffix])

    @staticmethod
    def _read_provided(root: Path) -> dict[str, tuple[str, ...]]:
        """A Python distribution's normalized name → the modules it provides, off the repository's `.venv`."""
        return {
            key_python(dist.name.removesuffix(".dist-info").rsplit("-", 1)[0]): modules_record(dist)
            for dist in sorted(root.glob(SITE))
        }

    @staticmethod
    def _read_index(root: Path, files: Iterable[Path]) -> dict[tuple[Ecosystem, str], list[str]]:
        """(world, module) → every source file importing it, sorted: one pass over the walked sources."""
        sources = ((path, SOURCES[path.suffix]) for path in files if path.suffix in SOURCES)
        rows = sorted(
            (ecosystem, module, path.relative_to(root).as_posix())
            for path, ecosystem in sources
            for module in MODULES[ecosystem](path.read_text(errors="replace"))
        )
        return {key: [path for *_, path in group] for key, group in itertools.groupby(rows, key=itemgetter(0, 1))}

    @staticmethod
    def _read_modules(ecosystem: Ecosystem, name: str, provided: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
        match ecosystem:
            case Ecosystem.PYTHON:
                return provided.get(key_python(name)) or (key_python(name).replace("-", "_"),)
            case Ecosystem.RUST:
                return (name.replace("-", "_"),)
            case _:
                return (name,)

    def _read_manifest(self, root: Path, file: str, manifest: Manifest) -> tuple[list[str], list[Dependency]]:
        """(files read, dependencies) of one root manifest and its lockfile; nothing when the manifest is absent."""
        path, lock = root / file, root / manifest.lock
        declared = manifest.declared(self._read_parsed(path)) if path.is_file() else []
        locked = manifest.locked(self._read_parsed(lock)) if declared and lock.is_file() else {}
        read = [name for name, there in ((file, path.is_file()), (manifest.lock, bool(locked))) if there]
        return read, [
            Dependency(
                name=name,
                ecosystem=manifest.ecosystem,
                manifest=file,
                scope=scope,
                declared=spec,
                resolved=locked.get(manifest.key(name), ""),
            )
            for name, scope, spec in declared
        ]

    def _read_compose(self, root: Path, path: Path) -> list[Dependency]:
        services = table_at(eserde.loads(path.read_text(), format=eserde.Format.YAML), ("services",))
        images = [(service, image_parts(str(spec["image"]))) for service, spec in services.items() if "image" in spec]
        return [
            Dependency(
                name=name,
                ecosystem=Ecosystem.CONTAINER,
                manifest=path.relative_to(root).as_posix(),
                scope=f"service:{service}",
                declared=version,
            )
            for service, (name, version) in images
        ]

    def _read_scan(self, root: Path) -> tuple[list[str], list[Dependency]]:
        """(manifests read, dependencies with their imports): the whole repository, in one sync pass."""
        files = list(self._read_files(root))
        manifests = [self._read_manifest(root, file, manifest) for file, manifest in MANIFESTS.items()]
        composes = [path for path in files if COMPOSE.match(path.name)]
        declared = [
            *(dependency for _, found in manifests for dependency in found),
            *(dependency for path in composes for dependency in self._read_compose(root, path)),
        ]
        index, provided = self._read_index(root, files), self._read_provided(root)
        linked = [
            (dependency, sorted({path for module in modules for path in index.get((dependency.ecosystem, module), ())}))
            for dependency in declared
            for modules in (self._read_modules(dependency.ecosystem, dependency.name, provided),)
        ]
        read = [
            *(file for files_read, _ in manifests for file in files_read),
            *(p.relative_to(root).as_posix() for p in composes),
        ]
        return read, [
            msgspec.structs.replace(dependency, imports=tuple(paths[:IMPORTS]), imported=len(paths))
            for dependency, paths in linked
        ]

    def _read_topic(self, topic: str) -> str:
        match topic in self._topics or not topic:
            case True:
                return topic
            case _:
                msg = f"topic {topic!r} is not in radar.yaml: {', '.join(sorted(self._topics)) or 'none declared'}"
                raise CompareError(msg)

    ############################################################

    ##### PUBLIC #####

    async def read(self, project: Path, query: str, topic: str = "") -> Stack:
        """The stack `project` declares, for `query`, on `topic` (empty: none given)."""
        kept = self._read_topic(topic)
        match await anyio.Path(project).is_dir():
            case False:
                msg = f"{project}: no such directory"
                raise CompareError(msg)
            case _:
                root = Path(await anyio.Path(project).resolve())
        manifests, dependencies = await anyio.to_thread.run_sync(self._read_scan, root)
        match dependencies:
            case []:
                msg = f"{root}: declares no dependency — read {', '.join(manifests) or 'no manifest'}"
                raise CompareError(msg)
            case _:
                return Stack(
                    project=str(root),
                    query=query,
                    topic=kept,
                    manifests=tuple(manifests),
                    dependencies=tuple(dependencies),
                )
