"""runtime.deps: injection by declared type — the one place ports meet adapters, built on demand, once per run.

This is the composition root of the hexagon: `SQLiteAdapter`, `FileCatalog` and `ShellProbe` are named here
and nowhere else; the store is wrapped in the undo journal and handed on as a bare `StorePort`, the catalog
and the probe reach the services as their ports. `Inject[T]` marks a parameter cyclopts must not parse (and `--help` must not show); the launcher resolves
each one from its type through `Deps.PROVIDERS`, a frozen table type → builder. A builder runs at most once
per run, and every resource it opens enters the run's exit stack, so edges close in reverse on the way out.
A command that never asks for the store never opens sqlite. Adding an injectable is one builder and one row in the table."""

from collections.abc import Awaitable, Callable, Mapping
from contextlib import AsyncExitStack
from types import MappingProxyType
from typing import Annotated, ClassVar, TypeVar, cast

from cyclopts import Parameter
from rich.console import Console

from adapters.ports import StorePort
from adapters.sqlite import SQLiteAdapter
from core.settings import settings as st
from core.state import State
from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.ports import CatalogPort, ProbePort
from e_taxis.adapters.probe import ShellProbe
from e_taxis.runtime.journal import StoreJournal
from e_taxis.runtime.settings import TaxisSettings
from e_taxis.services.doctor import DoctorService
from e_taxis.services.plan import PlanService
from e_taxis.services.resolver import ResolverService
from e_taxis.services.verify import VerifyService

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
        journal = StoreJournal(store, command=self._state.session.command, depth=st.cli.cli_history)
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
            DoctorService: _resolve_doctor,
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
