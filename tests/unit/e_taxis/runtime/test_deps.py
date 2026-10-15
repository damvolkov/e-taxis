"""tests/unit/e_taxis/runtime/deps: injection by type — built on first ask, once per run, unknown types refused."""

from contextlib import AsyncExitStack

import pytest

from adapters.ports import StorePort
from core.state import State
from e_taxis.models.session import Session
from e_taxis.runtime.deps import Deps
from e_taxis.runtime.journal import StoreJournal


def _state() -> State:
    return State(session=Session(command="test"))


async def test_deps_builds_each_kind_once_per_run() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        store = await deps.resolve(StorePort)
        assert store is await deps.resolve(StoreJournal)


async def test_deps_injects_by_name_from_the_declared_type() -> None:
    state = _state()
    async with AsyncExitStack() as stack:
        injected = await Deps(stack, state).inject({"graph": State})
    assert injected == {"graph": state}


async def test_deps_refuses_a_type_without_provider() -> None:
    async with AsyncExitStack() as stack:
        with pytest.raises(TypeError, match="no provider for int"):
            await Deps(stack, _state()).resolve(int)
