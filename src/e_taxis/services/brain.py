"""services.brain: the core installed into a harness's live tree — planned against what is there, written through
the journal, so `taxis history undo` puts every byte back.

The plan is three-way: what the render would land, what the tree holds, and what the last install wrote (its
digests, kept in the store under `brain:<target>`). A file the last install wrote and nobody touched since is an
`update`; one it did not write, or that was edited after, is an `overwrite` — shown before it happens, never
silent. Owned JSON keys go through the settings primitive's merge, so every other key of the file stays. MCP
registrations go through the harness's CLI; an update removes first and records how to put the old one back.
Nothing is ever deleted: what lives in a governed folder and the render no longer produces is an `orphan`."""

import asyncio
import hashlib
from typing import TYPE_CHECKING, Any, Final

import anyio
import msgspec

from e_taxis.adapters.disk import missing_dirs, read_file, write_file
from e_taxis.models.brain import BrainAction, BrainMove, BrainPlan
from e_taxis.models.error import BrainError, PrimitiveError
from e_taxis.models.journal import JournalCommand, JournalFile

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from adapters.ports import StorePort
    from e_taxis.adapters.ports import CorePort, HarnessPort, RecorderPort, RunnerPort
    from e_taxis.adapters.primitives.settings import SettingsPrimitive
    from e_taxis.models.brain import BrainFile, BrainKey, BrainRender, BrainServer
    from e_taxis.models.catalog import Target

##### DEFAULTS #####
PREFIX: str = "brain:"
MISSING: Final = object()

type Live = tuple[bytes, int] | None


##### TYPES #####
class BrainService:
    """The projections per target, the settings merge, the runner for registrations, the store for the record.

    `claude` is the tree (Claude Code's config dir); `registry` the file Claude keeps user-scope servers in."""

    __slots__ = ("_claude", "_harnesses", "_recorder", "_registry", "_runner", "_settings", "_store")

    def __init__(
        self,
        harnesses: Mapping[Target, HarnessPort],
        settings: SettingsPrimitive,
        runner: RunnerPort,
        store: StorePort,
        recorder: RecorderPort,
        *,
        claude: Path,
        registry: Path,
    ) -> None:
        self._harnesses = harnesses
        self._settings = settings
        self._runner = runner
        self._store = store
        self._recorder = recorder
        self._claude = claude
        self._registry = registry

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    async def _common_render(self, core: CorePort, target: Target) -> BrainRender:
        try:
            harness = self._harnesses[target]
        except KeyError:
            msg = f"no brain projection for {target} yet: shipped are {', '.join(self._harnesses)}"
            raise BrainError(msg) from None
        return harness.render(await core.load(), self._claude)

    async def _common_record(self, target: Target) -> dict[str, str]:
        raw = await self._store.get(f"{PREFIX}{target}")
        return {} if raw is None else msgspec.json.decode(raw, type=dict[str, str])

    async def _common_registered(self) -> dict[str, Any]:
        """User-scope servers as Claude stores them."""
        found = await read_file(self._registry)
        return {} if found is None else dict(msgspec.json.decode(found[0]).get("mcpServers", {}))

    def _plan_file(self, file: BrainFile, live: Live, record: Mapping[str, str]) -> BrainAction:
        match live:
            case None:
                return BrainAction.ADD
            case (data, _) if file.merged(data) == data:
                return BrainAction.FAITHFUL
            case (data, _) if record.get(file.path) == self._common_digest(data):
                return BrainAction.UPDATE
            case _:
                return BrainAction.OVERWRITE

    @staticmethod
    def _plan_value(live: Any, value: Any) -> BrainAction:
        match live:
            case _ if live is MISSING:
                return BrainAction.ADD
            case _ if live == value:
                return BrainAction.FAITHFUL
            case _:
                return BrainAction.UPDATE

    async def _plan_orphans(self, render: BrainRender) -> tuple[BrainMove, ...]:
        """Top entries of each governed folder (a skill dir, an agent file) that no rendered file lives under."""
        owned = {"/".join(file.path.split("/")[:2]) for file in render.files}
        found = sorted(
            [
                f"{folder}/{entry.name}"
                for folder in render.governed
                if await (root := anyio.Path(self._claude / folder)).is_dir()
                async for entry in root.iterdir()
            ]
        )
        return tuple(BrainMove(path=path, action=BrainAction.ORPHAN) for path in found if path not in owned)

    async def _common_plan(self, render: BrainRender, target: Target) -> tuple[BrainPlan, list[Live], dict[str, Any]]:
        record = await self._common_record(target)
        lives = list(await asyncio.gather(*(read_file(self._claude / file.path) for file in render.files)))
        documents = {key.file: await self._settings.read(self._claude / key.file) for key in render.keys}
        registered = await self._common_registered()
        moves = (
            *(
                BrainMove(path=file.path, action=self._plan_file(file, live, record))
                for file, live in zip(render.files, lives, strict=True)
            ),
            *(
                BrainMove(
                    path=f"{key.file}#{key.key}",
                    action=self._plan_value(documents[key.file].get(key.key, MISSING), key.value),
                )
                for key in render.keys
            ),
            *(
                BrainMove(
                    path=f"mcp:{server.name}",
                    action=self._plan_value(registered.get(server.name, MISSING), server.config),
                )
                for server in render.servers
            ),
            *await self._plan_orphans(render),
        )
        return (BrainPlan(target=target, tree=str(self._claude), moves=moves), lives, registered)

    async def _run_file(self, file: BrainFile, live: Live) -> None:
        target = self._claude / file.path
        created = await missing_dirs(target)
        await write_file(target, file.merged(None if live is None else live[0]))
        self._recorder.record(
            JournalFile(
                path=str(target),
                before=None if live is None else live[0],
                mode=None if live is None else live[1],
                created=created,
            )
        )

    async def _run_keys(self, keys: tuple[BrainKey, ...]) -> None:
        """One merge per file, the keys in render order."""
        _ = [
            self._recorder.record(
                *await self._settings.merge(
                    self._claude / name, tuple(((key.key,), key.value) for key in keys if key.file == name)
                )
            )
            for name in dict.fromkeys(key.file for key in keys)
        ]

    @staticmethod
    def _run_argv(name: str, config: Mapping[str, Any] | None) -> tuple[str, ...]:
        match config:
            case None:
                ### `claude mcp remove` takes no --scope (verified on Claude Code 2.1.296): the name alone.
                return ("claude", "mcp", "remove", name)
            case _:
                return ("claude", "mcp", "add-json", "--scope", "user", name, msgspec.json.encode(config).decode())

    async def _run_server(self, server: BrainServer, before: Mapping[str, Any] | None) -> None:
        add, remove = self._run_argv(server.name, server.config), self._run_argv(server.name, None)
        match before:
            case None:
                pass
            case old:
                await self._runner.run(remove)
                self._recorder.record(JournalCommand(argv=remove, undo=self._run_argv(server.name, old)))
        await self._runner.run(add)
        self._recorder.record(JournalCommand(argv=add, undo=remove))

    async def _run_moves(
        self, render: BrainRender, plan: BrainPlan, lives: list[Live], registered: Mapping[str, Any]
    ) -> None:
        """Files, then keys, then registrations; each change recorded the moment it lands."""
        moving = {move.path for move in plan.pending}
        _ = [
            await self._run_file(file, live)
            for file, live in zip(render.files, lives, strict=True)
            if file.path in moving
        ]
        await self._run_keys(tuple(key for key in render.keys if f"{key.file}#{key.key}" in moving))
        _ = [
            await self._run_server(server, registered.get(server.name))
            for server in render.servers
            if f"mcp:{server.name}" in moving
        ]

    ############################################################

    ##### PUBLIC #####

    async def plan(self, core: CorePort, target: Target) -> BrainPlan:
        """What installing the core would do to the tree. Writes nothing."""
        plan, _, _ = await self._common_plan(await self._common_render(core, target), target)
        return plan

    async def run(self, core: CorePort, target: Target) -> BrainPlan:
        """Land every pending move, then record what the tree now holds. A failure keeps what landed undoable."""
        render = await self._common_render(core, target)
        plan, lives, registered = await self._common_plan(render, target)
        try:
            await self._run_moves(render, plan, lives, registered)
        except (PrimitiveError, OSError) as exc:
            msg = f"brain install stopped: {exc} — `taxis history undo` reverts what landed"
            raise BrainError(msg) from exc
        landed = {
            file.path: self._common_digest(file.merged(None if live is None else live[0]))
            for file, live in zip(render.files, lives, strict=True)
        }
        await self._store.set(f"{PREFIX}{target}", msgspec.json.encode(landed))
        return plan
