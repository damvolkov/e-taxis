"""tests/unit/e_taxis/workflow/adapters/lock: one run at a time — held, re-entered by a child, and waited for.

Defect 8 of the legacy lock: a second run was refused outright. Now it waits (bounded), says once whom it waits
for, and runs the moment the first one lets go; only a lock held past the wait fails."""

from typing import TYPE_CHECKING, Any

import anyio
import pytest

from e_taxis.workflow.adapters.lock import FlockLock
from e_taxis.workflow.models.error import LockError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


async def test_lock_holds_names_itself_and_lets_go(tmp_path: Path) -> None:
    path = tmp_path / "reports" / ".lock"
    async with FlockLock(wait=0.0).hold(path, "workflow run r1") as token:
        assert path.read_text().startswith(f"{token} pid ")
        assert "workflow run r1" in path.read_text()
    assert path.read_text() == ""


async def test_lock_child_reenters_with_the_parent_token(tmp_path: Path) -> None:
    path = tmp_path / ".lock"
    async with (
        FlockLock(wait=0.0).hold(path, "parent") as token,
        FlockLock(wait=0.0, inherited=token).hold(path, "child") as again,
    ):
        assert again == token


async def test_lock_stale_token_is_no_mandate(tmp_path: Path, held: Callable[[Path], Any]) -> None:
    path = tmp_path / ".lock"
    async with held(path):
        with pytest.raises(LockError):
            async with FlockLock(wait=0.0, inherited="not-the-holder").hold(path, "child"):
                pass


async def test_lock_second_run_waits_then_runs(tmp_path: Path, held: Callable[[Path], Any]) -> None:
    path, said, order = tmp_path / ".lock", [], []

    async def first() -> None:
        async with held(path):
            await anyio.sleep(0.15)
            order.append("first done")

    async def second() -> None:
        await anyio.sleep(0.02)
        async with FlockLock(wait=2.0, poll=0.02, say=said.append).hold(path, "second"):
            order.append("second ran")

    async with anyio.create_task_group() as group:
        group.start_soon(first)
        group.start_soon(second)
    assert order == ["first done", "second ran"]
    assert len(said) == 1
    assert "another run" in said[0]


async def test_lock_held_past_the_wait_fails(tmp_path: Path, held: Callable[[Path], Any]) -> None:
    path = tmp_path / ".lock"
    async with held(path):
        with pytest.raises(LockError, match=r"held .* past 0s: .*another run"):
            async with FlockLock(wait=0.1, poll=0.02).hold(path, "second"):
                pass
