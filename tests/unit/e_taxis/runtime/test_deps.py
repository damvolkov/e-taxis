"""tests/unit/e_taxis/runtime/deps: injection by type — built on first ask, once per run, unknown types refused."""

from contextlib import AsyncExitStack

import pytest

from adapters.ports import StorePort
from core.state import State
from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.downloader import WreqDownloader
from e_taxis.adapters.ports import CatalogPort, ProbePort, RunnerPort, UndoPort
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.models.session import Session
from e_taxis.runtime.deps import Deps
from e_taxis.runtime.journal import StoreJournal
from e_taxis.services.apply import ApplyService
from e_taxis.services.doctor import DoctorService
from e_taxis.services.plan import PlanService
from e_taxis.services.uninstall import UninstallService
from e_taxis.services.verify import VerifyService


def _state() -> State:
    return State(session=Session(command="test"))


async def test_deps_builds_each_kind_once_per_run() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        store = await deps.resolve(StorePort)
        assert store is await deps.resolve(StoreJournal)
        assert (await deps.resolve(PlanService)) is await deps.resolve(PlanService)


async def test_deps_binds_the_taxis_ports_and_services() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await deps.resolve(CatalogPort), FileCatalog)
        assert isinstance(await deps.resolve(ProbePort), ProbePort)
        assert isinstance(await deps.resolve(VerifyService), VerifyService)
        assert isinstance(await deps.resolve(DoctorService), DoctorService)


async def test_deps_injects_by_name_from_the_declared_type() -> None:
    state = _state()
    async with AsyncExitStack() as stack:
        injected = await Deps(stack, state).inject({"graph": State})
    assert injected == {"graph": state}


async def test_deps_refuses_a_type_without_provider() -> None:
    async with AsyncExitStack() as stack:
        with pytest.raises(TypeError, match="no provider for int"):
            await Deps(stack, _state()).resolve(int)


async def test_deps_binds_the_writing_side(runner) -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await deps.resolve(ApplyService), ApplyService)
        assert isinstance(await deps.resolve(UninstallService), UninstallService)
        assert isinstance(await deps.resolve(UndoPort), UndoPort)
        assert await deps.resolve(RunnerPort) is runner


async def test_deps_real_runner_and_downloader_outside_the_sandbox() -> None:
    """The sandbox fixture swaps these two rows: the real builders are asked for directly."""
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await Deps._resolve_runner(deps), ProcessRunner)
        assert isinstance(await Deps._resolve_downloader(deps), WreqDownloader)
