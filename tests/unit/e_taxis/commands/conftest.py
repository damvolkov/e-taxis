"""tests/unit/e_taxis/commands: P1 commands never write, so a test files journal runs straight into the run's store."""

import asyncio
from typing import TYPE_CHECKING

import pytest

from adapters.sqlite import SQLiteAdapter
from e_taxis.runtime.journal import StoreJournal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


async def _file(command: str, writes: dict[str, bytes]) -> None:
    async with SQLiteAdapter() as store, StoreJournal(store, command=command, depth=50) as journal:
        _ = [await journal.set(key, value) for key, value in writes.items()]


@pytest.fixture
def filed() -> Callable[[str, dict[str, bytes]], None]:
    """File one run, as `command` would have written it, into the sqlite store the next `taxis` call opens."""
    return lambda command, writes: asyncio.run(_file(command, writes))


@pytest.fixture
def on_catalog(monkeypatch: pytest.MonkeyPatch, catalog_root: Path) -> Path:
    """Point every `taxis` run of the test at the sound fixture catalog."""
    monkeypatch.setenv("TAXIS_CATALOG", str(catalog_root))
    return catalog_root


@pytest.fixture
def on_doctor(monkeypatch: pytest.MonkeyPatch, doctor_root: Path) -> Path:
    """Point every `taxis` run of the test at the broken fixture catalog."""
    monkeypatch.setenv("TAXIS_CATALOG", str(doctor_root))
    return doctor_root
