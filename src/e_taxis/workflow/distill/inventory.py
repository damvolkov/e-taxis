"""distill.inventory: every plane a project can teach on, read without a model — what it has that the cores do not say.

The miners propose; this step makes sure they are asked about everything. It reads the project at the tip of the
run's branch (committed work only, never the checkout) against the published e-arkhetypo (`ref`, never its checkout)
and e-nous's lib.md files and MCP wiring, and writes one `Fact` per thing the cores lack or say differently:

- `library` — a dependency no skill's lib.md names (and which template systems already use it);
- `module` — a module of system core's layers the blueprint lacks, or one the project's copy diverged from;
- `common` — a shared project file (a system's `materials` in the blueprint manifest) the project changed;
- `service` — a service the project runs (compose, systemd units) that no stack service is;
- `project` — a top-level package no template system has, or a scaffold file that departs from its system's copy;
- `tooling` — an MCP server the project serves that the coders are not wired to;
- `ops` — a Make target, CI workflow, script, test tier or top-level folder no template has.

**Divergence is three-way.** The base is the template version the project was generated from: the commit its
`.templates.yaml` records, or — for a project older than the record — the version in the template's history closest
to the first copy the project committed. Against it a divergence is `ahead` (the project moved: a lesson may be
here), `behind` (the template moved: the project is stale) or `both`. What is behind, and what the project lost from
its template, goes to `stale` — drift to fix in the project, never a fact for the miners."""

import re
from difflib import unified_diff
from functools import partial, reduce
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.distill import Direction, Fact, FactStatus, Inventory, Manifest, Plane
from e_taxis.workflow.models.error import CommandError

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
LAYERS: Final[tuple[str, ...]] = ("adapters", "core", "ops", "processors")
TARGET: Final[re.Pattern[str]] = re.compile(r"^([A-Za-z0-9][\w-]*):(?!=)", re.MULTILINE)
NAME: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
COMPOSE: Final[re.Pattern[str]] = re.compile(r"(docker-)?compose[\w.-]*\.ya?ml")
SCAFFOLD: Final[tuple[str, ...]] = ("Dockerfile", "Makefile", "tach.toml", "pyproject.toml", "properdocs.yml")
TOOLS: Final[re.Pattern[str]] = re.compile(r"^\[tool\..*", re.MULTILINE | re.DOTALL)
DEFINITION: Final[re.Pattern[str]] = re.compile(r"^(?:async\s+def|def|class)\s+(\w+)", re.MULTILINE)
GATES: Final[tuple[str, ...]] = ("core-check", "common-check")
### where things sit in the two trees, by path shape: the captured segment is the name that counts.
STACKED: Final[re.Pattern[str]] = re.compile(r"stack/[^/]+/([^/]+)/.+")
SYSTEMS: Final[re.Pattern[str]] = re.compile(r"projects/python/([^/]+)/.*")
PACKAGES: Final[re.Pattern[str]] = re.compile(r"projects/python/[^/]+/[^/]+/[^/]+/([^/]+)/.+")
SKELETON: Final[re.Pattern[str]] = re.compile(r"projects/python/[^/]+/([^/]+)/.+")
TIERS: Final[re.Pattern[str]] = re.compile(r"projects/python/[^/]+/tests/([^/]+)/.+")
OWN_TIERS: Final[re.Pattern[str]] = re.compile(r"tests/([^/]+)/.+")
SOURCES: Final[re.Pattern[str]] = re.compile(r"src/([^/]+)/.+")
RECORD: str = ".templates.yaml"
MANIFEST: str = "projects/templates.yml"
SYSTEM: str = "projects/python/api"
GIT: float = 60.0


##### TYPES #####
class ScopeInventory(msgspec.Struct, frozen=True, kw_only=True):
    """What one inventory reads: the project at its tip, its origin, and the published blueprint."""

    project: Path
    head: str
    files: frozenset[str]
    package: str
    brand: str
    fresh: frozenset[str]
    tree: frozenset[str]
    systems: dict[str, dict[str, Any]]
    record: dict[str, Any]


class DistillInventory:
    """The project's branch tip against the published blueprint and e-nous's own lists."""

    __slots__ = ("_blueprint", "_command", "_harness", "_ref")

    def __init__(self, command: CommandPort, *, harness: Path, blueprint: Path, ref: str) -> None:
        self._command = command
        self._harness = harness
        self._blueprint = blueprint.expanduser()
        self._ref = ref

    ##### PRIVATE METHODS #####

    async def _common_git(self, repo: Path, *args: str) -> str:
        return await self._command.run("git", "-C", str(repo), *args, limit=GIT)

    async def _common_show(self, repo: Path, rev: str, path: str) -> str:
        try:
            return await self._common_git(repo, "show", f"{rev}:{path}")
        except CommandError:
            return ""

    async def _common_listing(self, repo: Path, rev: str) -> frozenset[str]:
        return frozenset((await self._common_git(repo, "ls-tree", "-r", "--name-only", rev)).splitlines())

    async def _common_theirs(self, path: str) -> str:
        return await self._common_show(self._blueprint, self._ref, path)

    async def _common_texts(self, name: str) -> list[str]:
        """Every file called `name` under e-nous's core, as text."""
        return [await path.read_text() async for path in anyio.Path(self._harness / "core").rglob(name)]

    @staticmethod
    def _common_fact(
        plane: Plane,
        subject: str,
        status: FactStatus,
        detail: str = "",
        where: str = "",
        *,
        fresh: bool = True,
        direction: Direction | None = None,
        base: str = "",
    ) -> Fact:
        return Fact(
            id=f"{plane}:{subject}",
            plane=plane,
            subject=subject,
            status=status,
            detail=detail,
            where=where,
            fresh=fresh,
            direction=direction,
            base=base,
        )

    @staticmethod
    def _common_names(pyproject: str) -> set[str]:
        """The distribution names a pyproject declares, runtime and every dependency group."""
        data = eserde.loads(pyproject, format=eserde.Format.TOML) if pyproject else {}
        groups = data.get("dependency-groups", {}).values()
        items = [*data.get("project", {}).get("dependencies", []), *(i for g in groups for i in g)]
        return {
            found.group(0).lower().replace("_", "-") for i in items if isinstance(i, str) and (found := NAME.match(i))
        }

    @staticmethod
    def _common_delta(ours: str, theirs: str) -> tuple[int, int]:
        lines = list(unified_diff(theirs.splitlines(), ours.splitlines(), lineterm="", n=0))
        added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
        return added, removed

    async def _base_recorded(self, commit: str, theirs: str, normal: Callable[[str], str]) -> tuple[str, str] | None:
        text = await self._common_show(self._blueprint, commit, theirs)
        return (commit, normal(text)) if text else None

    async def _base_rebuilt(
        self, scope: ScopeInventory, local: str, theirs: str, normal: Callable[[str], str]
    ) -> tuple[str, str] | None:
        """The template version closest to the first copy the project committed; None when the template has no history."""
        added = (
            await self._common_git(scope.project, "log", "--diff-filter=A", "--format=%H", scope.head, "--", local)
        ).split()
        ### pathspec filters before rename detection, so a file at head was always added somewhere; the head copy
        ### stands in should history say otherwise.
        copied = normal(await self._common_show(scope.project, added[-1] if added else scope.head, local))
        shas = (await self._common_git(self._blueprint, "log", "--format=%H", self._ref, "--", theirs)).split()
        versions = [(sha, normal(await self._common_show(self._blueprint, sha, theirs))) for sha in shas]
        return min(versions, key=lambda version: sum(self._common_delta(copied, version[1]))) if versions else None

    async def _common_base(
        self, scope: ScopeInventory, local: str, theirs: str, normal: Callable[[str], str]
    ) -> tuple[str, str] | None:
        """The template version the project copied, as (commit, text): recorded, or reconstructed from history."""
        match str(scope.record.get("commit", "")):
            case "":
                return await self._base_rebuilt(scope, local, theirs, normal)
            case commit:
                return await self._base_recorded(commit, theirs, normal)

    async def _common_defines(self, name: str) -> set[str]:
        """The files of system core that define `name` in the published tree (none: git grep exits 1)."""
        pattern = rf"^(async\s+def|def|class)\s+{name}\b"
        try:
            said = await self._common_git(
                self._blueprint, "grep", "-l", "-E", pattern, self._ref, "--", "projects/python/core/src"
            )
        except CommandError:
            return set()
        return {line.split(":", 1)[1] for line in said.splitlines()}

    async def _common_elsewhere(self, ours: str, was: str, theirs: str) -> str:
        """Where the template already defines what the project added: a move across files reads as `ahead` per file."""
        diff = unified_diff(was.splitlines(), ours.splitlines(), lineterm="", n=0)
        added = "\n".join(line[1:] for line in diff if line.startswith("+") and not line.startswith("+++"))
        homes = {name: await self._common_defines(name) - {theirs} for name in sorted(set(DEFINITION.findall(added)))}
        places = sorted({place for found in homes.values() for place in found})
        covered = sum(1 for found in homes.values() if found)
        return f" · {covered}/{len(homes)} of its new definitions already in {', '.join(places)}" if covered else ""

    async def _common_diverged(
        self,
        scope: ScopeInventory,
        *,
        plane: Plane,
        local: str,
        theirs: str,
        base: tuple[str, str],
        texts: tuple[str, str],
    ) -> Fact:
        """A divergence against a found base: who moved, by how much, and where the template already says it."""
        (commit, was), (ours, now) = base, texts
        mine, moved = self._common_delta(ours, was), self._common_delta(now, was)
        direction = Direction.BOTH if any(mine) and any(moved) else Direction.AHEAD if any(mine) else Direction.BEHIND
        elsewhere = (
            await self._common_elsewhere(ours, was, theirs)
            if plane is Plane.MODULE and direction is not Direction.BEHIND
            else ""
        ) + (" · removals only: what the generator pruned or the project does not use" if mine[0] == 0 else "")
        said = {
            Direction.AHEAD: f"project +{mine[0]} -{mine[1]} since base",
            Direction.BEHIND: f"template +{moved[0]} -{moved[1]} since base",
            Direction.BOTH: f"project +{mine[0]} -{mine[1]}, template +{moved[0]} -{moved[1]} since base",
        }[direction]
        return self._common_fact(
            plane,
            local,
            FactStatus.DIVERGED,
            f"{said} {commit[:7]} · {theirs}{elsewhere}",
            local,
            fresh=local in scope.fresh,
            direction=direction,
            base=commit,
        )

    async def _common_weigh(
        self, scope: ScopeInventory, plane: Plane, local: str, theirs: str, normal: Callable[[str], str]
    ) -> list[Fact]:
        """One shared file, three-way: nothing when equal; else its direction against the base, when one is found."""
        ours = normal(await self._common_show(scope.project, scope.head, local))
        now = normal(await self._common_theirs(theirs))
        match ours == now:
            case True:
                return []
            case _:
                base = await self._common_base(scope, local, theirs, normal)
        match base:
            case None:
                added, removed = self._common_delta(ours, now)
                detail = f"+{added} -{removed} vs {theirs}"
                return [self._common_fact(plane, local, FactStatus.DIVERGED, detail, local, fresh=local in scope.fresh)]
            case found:
                return [
                    await self._common_diverged(
                        scope, plane=plane, local=local, theirs=theirs, base=found, texts=(ours, now)
                    )
                ]

    @staticmethod
    def _common_system(scope: ScopeInventory) -> dict[str, Any]:
        """The template the project comes from: recorded, else the api system (the one most projects start from)."""
        source = str(scope.record.get("system", SYSTEM))
        return next((spec for spec in scope.systems.values() if spec.get("source") == source), {})

    async def _take_libraries(self, scope: ScopeInventory, base: str) -> list[Fact]:
        current = self._common_names(await self._common_show(scope.project, scope.head, "pyproject.toml"))
        before = self._common_names(await self._common_show(scope.project, base, "pyproject.toml"))
        docs = [text.lower() for text in await self._common_texts("lib.md")]
        systems = {
            path.split("/")[2]: self._common_names(await self._common_theirs(path))
            for path in sorted(scope.tree)
            if re.fullmatch(r"projects/python/[^/]+/pyproject\.toml", path)
        }
        return [
            self._common_fact(
                Plane.LIBRARY,
                name,
                FactStatus.ABSENT,
                "blueprint: " + (", ".join(sorted(s for s, names in systems.items() if name in names)) or "none"),
                "pyproject.toml",
                fresh=name not in before,
            )
            for name in sorted(current)
            if not any(
                re.search(rf"(?<![\w-]){re.escape(variant)}(?![\w-])", text)
                for text in docs
                for variant in {name, name.replace("-", "_")}
            )
        ]

    @staticmethod
    def _modules_normal(strip: re.Pattern[str], text: str) -> str:
        return strip.sub(r"\1", text)

    async def _take_modules(self, scope: ScopeInventory) -> list[Fact]:
        """Project core's layers, wherever the project keeps them: `src/<layer>/` as generated, or inside its package."""
        layout = re.compile(rf"src/(?:{re.escape(scope.package)}/)?((?:{'|'.join(LAYERS)})/.+\.py)")
        strip = re.compile(rf"\b(?:e_core|{re.escape(scope.package)})\.({'|'.join(LAYERS)})\b")
        normal = partial(self._modules_normal, strip)
        pairs = sorted(
            (local, f"projects/python/core/src/e_core/{found.group(1)}")
            for local in scope.files
            if (found := layout.fullmatch(local)) and not local.endswith("__init__.py")
        )
        absent = [
            self._common_fact(Plane.MODULE, local, FactStatus.ABSENT, "", local, fresh=local in scope.fresh)
            for local, theirs in pairs
            if theirs not in scope.tree
        ]
        weighed = [
            await self._common_weigh(scope, Plane.MODULE, local, theirs, normal)
            for local, theirs in pairs
            if theirs in scope.tree
        ]
        return [*absent, *(f for facts in weighed for f in facts)]

    async def _take_common(self, scope: ScopeInventory) -> list[Fact]:
        materials = [(m["src"], m["dst"]) for m in self._common_system(scope).get("materials", [])]
        missing = [
            self._common_fact(
                Plane.COMMON, local, FactStatus.MISSING, f"`make common` copies it from {source}", local, fresh=False
            )
            for source, local in materials
            if local not in scope.files
        ]
        weighed = [
            await self._common_weigh(scope, Plane.COMMON, local, source, str)
            for source, local in materials
            if local in scope.files
        ]
        return [*missing, *(f for facts in weighed for f in facts)]

    async def _take_services(self, scope: ScopeInventory) -> list[Fact]:
        stack = {found.group(1) for path in scope.tree if (found := STACKED.fullmatch(path))}
        own = {scope.brand, scope.brand.replace("-", "")}
        composes = sorted(f for f in scope.files if COMPOSE.fullmatch(PurePosixPath(f).name))
        declared = [
            (
                path,
                eserde.loads(await self._common_show(scope.project, scope.head, path), format=eserde.Format.YAML) or {},
            )
            for path in composes
        ]
        found = {
            **{name: path for path, data in declared for name in data.get("services", {})},
            **{PurePosixPath(f).stem: f for f in sorted(scope.files) if f.endswith(".service")},
        }
        return [
            self._common_fact(
                Plane.SERVICE,
                name,
                FactStatus.ABSENT,
                "no stack service of that name",
                where,
                fresh=where in scope.fresh,
            )
            for name, where in sorted(found.items())
            if name not in stack and name not in own
        ]

    @staticmethod
    def _take_projects(scope: ScopeInventory) -> list[Fact]:
        known = {
            found.group(1) for path in scope.tree for shape in (SYSTEMS, PACKAGES) if (found := shape.fullmatch(path))
        }
        prefix = f"src/{scope.package}/"
        packaged = re.compile(rf"{re.escape(prefix)}([^/]+)/.+")
        folders = sorted({found.group(1) for f in scope.files if (found := packaged.fullmatch(f))})
        return [
            DistillInventory._common_fact(
                Plane.PROJECT,
                folder,
                FactStatus.ABSENT,
                f"{sum(1 for f in scope.files if f.startswith(local + '/') and f.endswith('.py'))} modules; "
                "no template project has this package",
                local,
                fresh=any(f.startswith(local + "/") for f in scope.fresh),
            )
            for folder in folders
            if folder not in known
            for local in (f"{prefix}{folder}",)
        ]

    async def _take_tooling(self, scope: ScopeInventory) -> list[Fact]:
        wiring = " ".join(await self._common_texts("mcp.yaml"))
        serves = any(f.startswith(f"src/{scope.package}/mcp/") for f in scope.files)
        fact = self._common_fact(
            Plane.TOOLING, scope.brand, FactStatus.ABSENT, "serves an MCP the coders are not wired to"
        )
        return [fact] if serves and scope.brand not in wiring else []

    async def _take_ops(self, scope: ScopeInventory) -> list[Fact]:
        makefiles = sorted(p for p in scope.tree if re.fullmatch(r"projects/python/[^/]+/Makefile", p))
        targets = {t for p in makefiles for t in TARGET.findall(await self._common_theirs(p))}
        ours = TARGET.findall(await self._common_show(scope.project, scope.head, "Makefile"))
        system = self._common_system(scope).get("source", SYSTEM)
        gates = [t for t in GATES if t in TARGET.findall(await self._common_theirs(f"{system}/Makefile"))]
        skeleton = {found.group(1) for path in scope.tree if (found := SKELETON.fullmatch(path))}
        tiers = {found.group(1) for path in scope.tree if (found := TIERS.fullmatch(path))}
        names = {PurePosixPath(path).name for path in scope.tree}
        folders = sorted({f.split("/")[0] for f in scope.files if "/" in f} - skeleton - {".github"})
        flows = sorted(
            f for f in scope.files if f.startswith(".github/workflows/") and PurePosixPath(f).name not in names
        )
        scripts = sorted(f for f in scope.files if f.startswith("scripts/") and PurePosixPath(f).name not in names)
        ours_tiers = sorted({found.group(1) for f in scope.files if (found := OWN_TIERS.fullmatch(f))} - tiers)
        fact, fresh = self._common_fact, scope.fresh
        return [
            *(
                fact(
                    Plane.OPS,
                    f"make {t}",
                    FactStatus.ABSENT,
                    "no template Makefile has it",
                    "Makefile",
                    fresh="Makefile" in fresh,
                )
                for t in dict.fromkeys(ours)
                if t not in targets
            ),
            *(
                fact(
                    Plane.OPS,
                    f"make {t}",
                    FactStatus.MISSING,
                    f"the drift gate {system}'s Makefile has",
                    "Makefile",
                    fresh=False,
                )
                for t in gates
                if t not in ours
            ),
            *(
                []
                if scope.record
                else [
                    fact(Plane.OPS, RECORD, FactStatus.MISSING, "no origin recorded: the base is rebuilt from history")
                ]
            ),
            *(
                fact(
                    Plane.OPS,
                    f"{d}/",
                    FactStatus.ABSENT,
                    "a top-level folder no template system has",
                    d,
                    fresh=any(f.startswith(d + "/") for f in fresh),
                )
                for d in folders
            ),
            *(
                fact(Plane.OPS, f, FactStatus.ABSENT, "a CI workflow no template has", f, fresh=f in fresh)
                for f in flows
            ),
            *(fact(Plane.OPS, f, FactStatus.ABSENT, "a script no template has", f, fresh=f in fresh) for f in scripts),
            *(
                fact(
                    Plane.OPS,
                    f"tests/{t}/",
                    FactStatus.ABSENT,
                    "a test tier no template has",
                    f"tests/{t}",
                    fresh=any(f.startswith(f"tests/{t}/") for f in fresh),
                )
                for t in ours_tiers
            ),
        ]

    @staticmethod
    def _scaffold_normal(name: str, pairs: tuple[tuple[str, str], ...], text: str) -> str:
        """A scaffold file with names generalized; a pyproject reduced to its `[tool.*]` part."""
        body = (found.group(0) if (found := TOOLS.search(text)) else "") if name == "pyproject.toml" else text
        return reduce(lambda done, pair: done.replace(*pair), (pair for pair in pairs if pair[0]), body)

    async def _take_scaffold(self, scope: ScopeInventory) -> list[Fact]:
        """Each scaffold file against its system's copy, three-way (pyproject: its `[tool.*]` part only)."""
        spec = self._common_system(scope)
        source = spec.get("source", SYSTEM)
        pairs = (
            (scope.package, "<package>"),
            (spec.get("package", ""), "<package>"),
            (scope.brand, "<brand>"),
            (spec.get("brand", ""), "<brand>"),
        )
        weighed = [
            await self._common_weigh(
                scope, Plane.PROJECT, name, f"{source}/{name}", partial(self._scaffold_normal, name, pairs)
            )
            for name in SCAFFOLD
            if name in scope.files and f"{source}/{name}" in scope.tree
        ]
        return [f for facts in weighed for f in facts]

    async def _take_scope(self, manifest: Manifest) -> ScopeInventory:
        project, head = Path(manifest.scope.project), manifest.scope.branches[0]
        files = await self._common_listing(project, head)
        packages = sorted({found.group(1) for f in files if (found := SOURCES.fullmatch(f))} - set(LAYERS))
        record = await self._common_show(project, head, RECORD)
        templates = await self._common_theirs(MANIFEST)
        return ScopeInventory(
            project=project,
            head=head,
            files=files,
            package=packages[0] if len(packages) == 1 else "",
            brand=project.name,
            fresh=frozenset(f.path for f in manifest.files),
            tree=await self._common_listing(self._blueprint, self._ref),
            systems=(eserde.loads(templates, format=eserde.Format.YAML) or {}).get("templates", {})
            if templates
            else {},
            record=(eserde.loads(record, format=eserde.Format.YAML) or {}) if record else {},
        )

    ############################################################

    ##### PUBLIC #####

    async def take(self, manifest: Manifest) -> Inventory:
        """The facts of the run's first branch at its tip, and where that tip is behind its blueprint."""
        scope = await self._take_scope(manifest)
        packaged = bool(scope.package)
        found = [
            *await self._take_libraries(scope, manifest.scope.base),
            *(await self._take_modules(scope) if packaged else []),
            *await self._take_common(scope),
            *await self._take_services(scope),
            *(self._take_projects(scope) if packaged else []),
            *(await self._take_tooling(scope) if packaged else []),
            *await self._take_ops(scope),
            *await self._take_scaffold(scope),
        ]
        unique = list({f.id: f for f in found}.values())
        stale = {f.id for f in unique if f.direction is Direction.BEHIND or f.status is FactStatus.MISSING}
        return Inventory(
            facts=tuple(f for f in unique if f.id not in stale), stale=tuple(f for f in unique if f.id in stale)
        )
