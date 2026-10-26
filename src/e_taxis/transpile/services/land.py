"""services.land: a projection landed in a live tree — planned against what is there, written through the journal.

The plan reads every target the projection names under `<home>/<tree>`, every file of the spec's governed
directories, and the registry's live entries, then holds them to the render fragment by fragment (`engine.plan`).
Landing writes each target that moves (atomically; a link is replaced by a real file), removes each stale governed
file, and syncs the registry through the harness's own CLI (`apply.add` / `apply.remove`, HOME pinned). Every change
is a journal effect the moment it lands, so `taxis history undo` reverts a landing — a failed one included. Last,
what landed is recorded (`transpile:<backend>`: commit, model, spec, a digest per file and per registry entry): the
base of the three-way reverse."""

import hashlib
import shlex
from functools import partial
from typing import TYPE_CHECKING, Any

import anyio
import msgspec

from e_taxis.adapters.disk import missing_dirs, read_file, remove_file, write_file
from e_taxis.harness.models.journal import JournalCommand, JournalFile
from e_taxis.transpile.engine.encode import match_target
from e_taxis.transpile.engine.model import SpecModel
from e_taxis.transpile.engine.plan import governed_plan, land_plan, registry_plan, rendered_plan, target_plan
from e_taxis.transpile.engine.reverse import digest_reverse
from e_taxis.transpile.models.report import Report, ReportFinding, ReportKind
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from e_taxis.adapters.ports import StorePort
    from e_taxis.harness.models.ports import RecorderPort, RunnerPort
    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import NousPort
    from e_taxis.transpile.models.projection import Projection

##### DEFAULTS #####
PREFIX: str = "transpile:"
MOVES: frozenset[ReportKind] = frozenset({ReportKind.MISSING, ReportKind.DRIFT, ReportKind.SYMLINK})


##### TYPES #####
class LandService:
    """The render it lands, the runner for registrations, the store for the record, the recorder for undo."""

    __slots__ = ("_recorder", "_runner", "_shell", "_store")

    def __init__(self, runner: RunService, shell: RunnerPort, store: StorePort, recorder: RecorderPort) -> None:
        self._runner = runner
        self._shell = shell
        self._store = store
        self._recorder = recorder

    ##### PRIVATE METHODS #####

    @staticmethod
    def _plan_registry_live(home: Path, target: Mapping[str, Any]) -> dict[str, Any]:
        """The registry's entries as the harness stores them: `apply.read` is `<file under HOME>#<key>`."""
        file, _, key = target["apply"]["read"].partition("#")
        path = home / file
        match path.is_file():
            case False:
                return {}
            case _:
                found = msgspec.json.decode(path.read_bytes())
                return dict(found.get(key) or {}) if isinstance(found, dict) else {}

    @staticmethod
    async def _plan_governed(tree: Path, govern: list[str]) -> list[str]:
        """Every live file under the governed directories, relative to the tree; a linked directory is not swept."""
        return [
            str(path.relative_to(tree))
            for folder in govern
            if (root := tree / folder).is_dir() and not root.is_symlink()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]

    async def _plan_file(
        self, backend: str, path: str, target: Mapping[str, Any], projection: Projection, tree: Path
    ) -> tuple[bytes, bytes | None, list[ReportFinding]]:
        live_path = anyio.Path(tree / path)
        found = await read_file(tree / path)
        live = None if found is None else found[0]
        placements = projection.placements[path]
        landed = land_plan(
            target.get("format", "file"), projection.files[path], live, target.get("foreign", []), placements
        )
        findings = list(target_plan(backend, path, target, placements, landed=landed, live=live))
        link = (
            [
                ReportFinding(
                    kind=ReportKind.SYMLINK,
                    backend=backend,
                    where=placements[0].origin,
                    path=path,
                    detail="a link: replaced by a real file",
                )
            ]
            if await live_path.is_symlink()
            else []
        )
        return landed, live, [*findings, *link]

    async def _plan(
        self, nous: NousPort, backend: str, home: Path
    ) -> tuple[
        Report,
        dict[str, bytes],
        dict[str, bytes],
        list[str],
        dict[str, dict[str, Any]],
        Projection,
        NousTree,
        Mapping[str, Any],
    ]:
        spec_tree, projection = await self._runner.project(
            nous, backend, home / RunService.spec(await nous.load(), backend)["tree"]
        )
        spec = RunService.spec(spec_tree, backend)
        tree = home / spec["tree"]
        files = [(path, match_target(path, spec["targets"])) for path in projection.files]
        planned = [(path, await self._plan_file(backend, path, target, projection, tree)) for path, target in files]
        governed = await self._plan_governed(tree, spec.get("govern", []))
        foreign = [entry["path"] for entry in spec.get("foreign", [])]
        stale = list(governed_plan(backend, spec.get("govern", []), foreign, list(projection.files), governed))
        registry = {
            name: self._plan_registry_live(home, match_target(name, spec["targets"])) for name in projection.registry
        }
        registry_findings = [
            finding
            for name in projection.registry
            for finding in registry_plan(backend, name, projection.placements[name], registry[name])
        ]
        links = [
            finding
            for path, to in projection.links.items()
            for finding in await self._plan_link(backend, path, tree / to, tree / path, projection)
        ]
        findings = (*(finding for _, (_, _, found) in planned for finding in found), *links, *stale, *registry_findings)
        report = Report(stamp=CheckService.stamp(spec_tree, SpecModel(spec_tree.base).version), findings=findings)
        landed = {path: data for path, (data, _, _) in planned}
        writes = {path: landed[path] for path, (_, _, found) in planned if found}
        removals = [finding.path for finding in stale]
        return report, landed, writes, removals, registry, projection, spec_tree, spec

    @staticmethod
    async def _plan_link(backend: str, path: str, to: Path, link: Path, projection: Projection) -> list[ReportFinding]:
        """A link target: missing, or a link elsewhere / a real file in its place (drift)."""
        where = projection.placements[path][0].origin if projection.placements.get(path) else "—"
        live = anyio.Path(link)
        match (await live.is_symlink(), await live.exists()):
            case (True, _) if str(await live.readlink()) == str(to):
                return []
            case (False, False):
                return [
                    ReportFinding(
                        kind=ReportKind.MISSING, backend=backend, where=where, path=path, detail=f"a link to {to}"
                    )
                ]
            case _:
                return [
                    ReportFinding(
                        kind=ReportKind.DRIFT, backend=backend, where=where, path=path, detail=f"should link to {to}"
                    )
                ]

    async def _land_link(self, link: Path, to: Path) -> None:
        """The link made, whatever stood there recorded first so undo puts it back."""
        found = None if await anyio.Path(link).is_symlink() else await read_file(link)
        created = await missing_dirs(link)
        await anyio.Path(link).parent.mkdir(parents=True, exist_ok=True)
        await anyio.Path(link).unlink(missing_ok=True)
        await anyio.Path(link).symlink_to(to)
        self._recorder.record(
            JournalFile(
                path=str(link),
                before=None if found is None else found[0],
                mode=None if found is None else found[1],
                created=created,
            )
        )

    async def _land_write(self, path: Path, data: bytes) -> None:
        found = await read_file(path)
        created = await missing_dirs(path)
        await write_file(path, data)
        self._recorder.record(
            JournalFile(
                path=str(path),
                before=None if found is None else found[0],
                mode=None if found is None else found[1],
                created=created,
            )
        )

    async def _land_remove(self, path: Path) -> None:
        match await read_file(path):
            case None:
                return
            case found:
                await remove_file(path)
                self._recorder.record(JournalFile(path=str(path), before=found[0], mode=found[1]))

    @staticmethod
    def _land_argv(template: str, home: Path, **values: str) -> tuple[str, ...]:
        """A registry command from its spec template, HOME pinned so it lands where the plan read."""
        return (
            "env",
            "-u",
            "CLAUDE_CONFIG_DIR",
            f"HOME={home}",
            *(values.get(token[1:-1], token) if token.startswith("{") else token for token in shlex.split(template)),
        )

    def _land_commands(
        self, home: Path, apply: Mapping[str, str], entries: Mapping[str, Any], current: Mapping[str, Any]
    ) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        """(command, its undo) for every entry that moves: a changed one removed then re-added, a stray one removed."""
        add = partial(self._land_add, apply["add"], home)
        remove = partial(self._land_argv, apply["remove"], home)
        changed = [(entry, value) for entry, value in entries.items() if current.get(entry) != value]
        return [
            *(
                pair
                for entry, value in changed
                for pair in (
                    *(((remove(name=entry), add(entry, current[entry])),) if entry in current else ()),
                    (add(entry, value), remove(name=entry)),
                )
            ),
            *((remove(name=entry), add(entry, current[entry])) for entry in current if entry not in entries),
        ]

    @classmethod
    def _land_add(cls, template: str, home: Path, entry: str, value: Any) -> tuple[str, ...]:
        return cls._land_argv(template, home, name=entry, json=msgspec.json.encode(value).decode())

    async def _land_command(self, argv: tuple[str, ...], undo: tuple[str, ...]) -> None:
        await self._shell.run(argv)
        self._recorder.record(JournalCommand(argv=argv, undo=undo))

    async def _land_registry(
        self, home: Path, spec: Mapping[str, Any], projection: Projection, live: Mapping[str, Mapping[str, Any]]
    ) -> None:
        commands = [
            pair
            for name, entries in projection.registry.items()
            for pair in self._land_commands(home, match_target(name, spec["targets"])["apply"], entries, live[name])
        ]
        _ = [await self._land_command(argv, undo) for argv, undo in commands]

    ############################################################

    ##### PUBLIC #####

    async def plan(self, nous: NousPort, backend: str, home: Path) -> Report:
        """What landing `backend` in `<home>/<tree>` would change. Writes nothing."""
        report, *_ = await self._plan(nous, backend, home)
        return report

    async def apply(self, nous: NousPort, backend: str, home: Path) -> Report:
        """Land every move, prune every stale governed file, sync the registry; record what landed. Undoable."""
        report, landed, writes, removals, live, projection, tree, spec = await self._plan(nous, backend, home)
        root = home / spec["tree"]
        _ = [await self._land_write(root / path, data) for path, data in writes.items()]
        _ = [await self._land_remove(root / path) for path in removals]
        moved = {finding.path for finding in report.findings}
        _ = [await self._land_link(root / path, root / to) for path, to in projection.links.items() if path in moved]
        await self._land_registry(home, spec, projection, live)
        record = {
            "commit": tree.commit,
            "spec": str(spec.get("spec", "")),
            "files": {path: hashlib.sha256(data).hexdigest() for path, data in landed.items()},
            "fragments": {
                f"{path}#{fragment}" if fragment else path: digest_reverse(value)
                for path in landed
                for fragment, value in rendered_plan(
                    match_target(path, spec["targets"]).get("format", "file"), projection.placements[path]
                ).items()
            },
            "registry": {
                f"{name}#{entry}": hashlib.sha256(msgspec.json.encode(value)).hexdigest()
                for name, entries in projection.registry.items()
                for entry, value in entries.items()
            },
        }
        await self._store.set(f"{PREFIX}{backend}", msgspec.json.encode(record))
        return report
