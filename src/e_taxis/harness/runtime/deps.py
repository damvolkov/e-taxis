"""runtime.deps: injection by declared type — the one place ports meet adapters, built on demand, once per run.

This is the composition root of the hexagon: `SQLiteAdapter`, `FileCatalog`, `ShellProbe`, the runner, the
downloader and every primitive adapter are named here and nowhere else; the store is wrapped in the undo
journal and handed on as a bare `StorePort` (and as the services' recorder), the catalog and the probe reach
the services as their ports, the primitives as one frozen table Primitive → adapter, the brain's projections as
one frozen table Target → harness adapter. The run's home, Claude's config dir and the environment (gate
secrets are named by the catalog, so they are read here, once) are resolved here too. `Inject[T]` marks a parameter cyclopts must not parse (and `--help` must not show); the launcher resolves
each one from its type through `Deps.PROVIDERS`, a frozen table type → builder. A builder runs at most once
per run, and every resource it opens enters the run's exit stack, so edges close in reverse on the way out.
A command that never asks for the store never opens sqlite. Adding an injectable is one builder and one row in the table."""

import os
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar, TypeVar, cast

from cyclopts import Parameter
from rich.console import Console

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.downloader import WreqDownloader
from e_taxis.adapters.harness.claudecode import ClaudecodeHarness
from e_taxis.adapters.ports import StorePort
from e_taxis.adapters.primitives.binary import BinaryPrimitive
from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.adapters.primitives.file import FilePrimitive
from e_taxis.adapters.primitives.mcp import McpPrimitive
from e_taxis.adapters.primitives.npm import NpmPrimitive
from e_taxis.adapters.primitives.plugin import PluginPrimitive
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.adapters.primitives.uv import UvPrimitive
from e_taxis.adapters.probe import ShellProbe
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.adapters.sqlite import SQLiteAdapter
from e_taxis.adapters.undo import EffectUndo
from e_taxis.core.settings import settings as st
from e_taxis.core.state import State
from e_taxis.harness.models.catalog import Primitive, Target
from e_taxis.harness.models.ports import (
    CatalogPort,
    DownloaderPort,
    HarnessPort,
    PrimitivePort,
    ProbePort,
    RunnerPort,
    UndoPort,
)
from e_taxis.harness.runtime.journal import StoreJournal
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.harness.services.apply import ApplyService
from e_taxis.harness.services.brain import BrainService
from e_taxis.harness.services.doctor import DoctorService
from e_taxis.harness.services.plan import PlanService
from e_taxis.harness.services.resolver import ResolverService
from e_taxis.harness.services.uninstall import UninstallService
from e_taxis.harness.services.verify import VerifyService
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService

T = TypeVar("T")
### cyclopts reads `Annotated` metadata but does not unwrap PEP 695 `type` aliases: the classic generic alias is what it sees.
Inject = Annotated[T, Parameter(parse=False)]

type Builder = Callable[[Deps], Awaitable[object]]


##### TYPES #####
class Deps:
    """The run's provider: builds what a command declares, caches it for the run, owns nothing past the stack."""

    __slots__ = ("_built", "_stack", "_state")

    def __init__(self, stack: AsyncExitStack, state: State) -> None:
        self._stack = stack
        self._state = state
        self._built: dict[Builder, object] = {}

    ##### PRIVATE METHODS #####

    async def _resolve_state(self) -> State:
        return self._state

    async def _resolve_console(self) -> Console:
        return Console()

    async def _resolve_store(self) -> StoreJournal:
        """The local store behind the undo journal: every command write is revertible by construction."""
        store = await self._stack.enter_async_context(SQLiteAdapter())
        world = await self.resolve(UndoPort)
        journal = StoreJournal(store, world=world, command=self._state.session.command, depth=st.cli.cli_history)
        return await self._stack.enter_async_context(journal)

    async def _resolve_settings(self) -> TaxisSettings:
        return TaxisSettings()

    async def _resolve_catalog(self) -> FileCatalog:
        return FileCatalog((await self.resolve(TaxisSettings)).taxis_catalog)

    async def _resolve_probe(self) -> ShellProbe:
        return ShellProbe(timeout=(await self.resolve(TaxisSettings)).taxis_timeout)

    async def _resolve_resolver(self) -> ResolverService:
        return ResolverService(await self.resolve(CatalogPort))

    async def _resolve_plan(self) -> PlanService:
        return PlanService(await self.resolve(ResolverService), await self.resolve(ProbePort))

    async def _resolve_verify(self) -> VerifyService:
        return VerifyService(await self.resolve(ResolverService), await self.resolve(ProbePort))

    async def _resolve_doctor(self) -> DoctorService:
        return DoctorService(await self.resolve(CatalogPort))

    async def _resolve_runner(self) -> ProcessRunner:
        return ProcessRunner()

    async def _resolve_downloader(self) -> WreqDownloader:
        return WreqDownloader(timeout=(await self.resolve(TaxisSettings)).taxis_download_timeout)

    async def _resolve_undo(self) -> EffectUndo:
        return EffectUndo(await self.resolve(RunnerPort), SettingsPrimitive(), FilePrimitive())

    async def _common_primitives(self) -> Mapping[Primitive, PrimitivePort]:
        """One adapter per primitive; `env` is the settings primitive's env merge under its own name."""
        settings, runner = await self.resolve(TaxisSettings), await self.resolve(RunnerPort)
        merge = SettingsPrimitive()
        return MappingProxyType(
            {
                Primitive.BINARY: BinaryPrimitive(await self.resolve(DownloaderPort), runner, settings.taxis_temp),
                Primitive.UV_TOOL: UvPrimitive(runner),
                Primitive.NPM: NpmPrimitive(runner, settings.taxis_npm_prefix),
                Primitive.SETTINGS: merge,
                Primitive.ENV: merge,
                Primitive.FILE: FilePrimitive(),
                Primitive.CLAUDE_MCP: McpPrimitive(runner),
                Primitive.CLAUDE_PLUGIN: PluginPrimitive(runner),
                Primitive.COMPOSE: ComposePrimitive(),
            }
        )

    async def _common_homes(self) -> tuple[Path, Path]:
        """(home, Claude's config dir): `~` and `~/.claude` as this run resolves them."""
        home = Path.home()
        return (home, (await self.resolve(TaxisSettings)).claude_config_dir or home / ".claude")

    async def _resolve_apply(self) -> ApplyService:
        home, claude = await self._common_homes()
        return ApplyService(
            await self.resolve(ResolverService),
            await self.resolve(PlanService),
            await self.resolve(ProbePort),
            await self._common_primitives(),
            await self.resolve(StoreJournal),
            home=home,
            claude=claude,
            environ=os.environ,
        )

    async def _resolve_brain(self) -> BrainService:
        """One projection per harness that has one; the run's store is both the record and the recorder.

        Claude keeps user-scope servers in `~/.claude.json` — inside CLAUDE_CONFIG_DIR whenever it is set, even
        to `~/.claude` (seen on Claude Code 2.1.296)."""
        home, claude = await self._common_homes()
        relocated = (await self.resolve(TaxisSettings)).claude_config_dir
        registry = relocated / ".claude.json" if relocated else home / ".claude.json"
        journal = await self.resolve(StoreJournal)
        harnesses: Mapping[Target, HarnessPort] = MappingProxyType({Target.CLAUDECODE: ClaudecodeHarness()})
        return BrainService(
            harnesses,
            SettingsPrimitive(),
            await self.resolve(RunnerPort),
            journal,
            journal,
            claude=claude,
            registry=registry,
        )

    async def _resolve_check(self) -> CheckService:
        return CheckService()

    async def _resolve_run(self) -> RunService:
        return RunService(await self.resolve(CheckService))

    async def _resolve_uninstall(self) -> UninstallService:
        home, claude = await self._common_homes()
        return UninstallService(
            await self.resolve(ResolverService),
            await self.resolve(ProbePort),
            await self._common_primitives(),
            await self.resolve(StoreJournal),
            home=home,
            claude=claude,
        )

    ############################################################

    ##### PUBLIC #####

    PROVIDERS: ClassVar[Mapping[type, Builder]] = MappingProxyType(
        {
            State: _resolve_state,
            Console: _resolve_console,
            StorePort: _resolve_store,
            StoreJournal: _resolve_store,
            TaxisSettings: _resolve_settings,
            CatalogPort: _resolve_catalog,
            ProbePort: _resolve_probe,
            ResolverService: _resolve_resolver,
            PlanService: _resolve_plan,
            VerifyService: _resolve_verify,
            CheckService: _resolve_check,
            RunService: _resolve_run,
            DoctorService: _resolve_doctor,
            RunnerPort: _resolve_runner,
            DownloaderPort: _resolve_downloader,
            UndoPort: _resolve_undo,
            ApplyService: _resolve_apply,
            BrainService: _resolve_brain,
            UninstallService: _resolve_uninstall,
        }
    )

    async def resolve[K](self, kind: type[K]) -> K:
        """The run's single instance of `kind`, built on first ask."""
        try:
            build = self.PROVIDERS[kind]
        except KeyError:
            msg = f"no provider for {kind.__name__}: add a builder to Deps.PROVIDERS"
            raise TypeError(msg) from None
        match build in self._built:
            case False:
                self._built[build] = await build(self)
            case _:
                pass
        return cast("K", self._built[build])

    async def inject(self, wanted: Mapping[str, type]) -> dict[str, object]:
        """Every non-parsed parameter of a command, by name, resolved from its declared type."""
        return {name: await self.resolve(kind) for name, kind in wanted.items()}
