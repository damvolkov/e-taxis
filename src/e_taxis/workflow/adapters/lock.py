"""adapters.lock: one workflow run at a time per e-nous checkout — an flock on `<nous>/.reports/.lock`, waited for.

Two runs at once would share the working tree their steps read and write. The lock is advisory and kernel-held: it
dies with its process, so no stale lock survives a crash. A second run does not give up: it waits, polling, for at
most `wait` seconds, says once whom it waits for, and only then fails. The holder hands its token to its children
(`TAXIS_LOCK`), so a step that starts a nested `taxis workflow run` re-enters instead of deadlocking on itself."""

import datetime as dt
import fcntl
import os
import uuid
from contextlib import asynccontextmanager
from typing import IO, TYPE_CHECKING

import anyio

from e_taxis.workflow.models.error import LockError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

##### DEFAULTS #####
POLL: float = 1.0


##### TYPES #####
class FlockLock:
    """Satisfies LockPort. `inherited` is the token a parent run handed down; `say` hears the one waiting line."""

    __slots__ = ("_inherited", "_poll", "_say", "_wait")

    def __init__(
        self, wait: float, inherited: str = "", poll: float = POLL, say: Callable[[str], object] | None = None
    ) -> None:
        self._wait = wait
        self._inherited = inherited
        self._poll = poll
        self._say = say or (lambda _: None)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _hold_try(handle: IO[str]) -> bool:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    async def _hold_attempt(self, handle: IO[str], attempt: int, path: Path) -> bool:
        """One try; the first refusal says who holds the lock, every later try comes one poll after the last."""
        _ = attempt and await anyio.sleep(self._poll)
        held = self._hold_try(handle)
        _ = (
            attempt == 0
            and not held
            and self._say(f"waiting up to {self._wait:.0f}s for {path}: {self._hold_holder(path)}")
        )
        return held

    @staticmethod
    def _hold_holder(path: Path) -> str:
        return path.read_text().strip().partition(" ")[2] or "unknown"

    async def _hold_inherited(self, path: Path) -> bool:
        """Whether this process descends from the holder: the token it was handed is the one on disk."""
        found = await anyio.Path(path).exists()
        return bool(self._inherited) and found and (await anyio.Path(path).read_text()).startswith(self._inherited)

    ############################################################

    ##### PUBLIC #####

    @asynccontextmanager
    async def hold(self, path: Path, command: str) -> AsyncIterator[str]:
        """Hold `path` for the block and yield the token children inherit; re-enter when the parent holds it."""
        match await self._hold_inherited(path):
            case True:
                yield self._inherited
                return
            case _:
                pass
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        attempts = int(self._wait // self._poll) + 1
        with path.open("a+") as handle:
            tries = (attempt for attempt in range(attempts) if await self._hold_attempt(handle, attempt, path))
            match await anext(tries, None):
                case None:
                    msg = f"another run held {path} past {self._wait:.0f}s: {self._hold_holder(path)}"
                    raise LockError(msg)
                case _:
                    pass
            token = uuid.uuid4().hex
            handle.seek(0)
            handle.truncate()
            handle.write(f"{token} pid {os.getpid()} · {command} · {dt.datetime.now(dt.UTC):%Y-%m-%dT%H:%M:%SZ}\n")
            handle.flush()
            try:
                yield token
            finally:
                handle.seek(0)
                handle.truncate()
                fcntl.flock(handle, fcntl.LOCK_UN)
