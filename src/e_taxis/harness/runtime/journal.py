"""runtime.journal: undo for free — a StorePort decorator that records what every write overwrote, and the
recorder the writing services hand every world effect to.

A command writes through `StoreJournal` believing it is the store. The first write to each key records
the value it held; on a clean exit the run is filed as one `Journal` entry. A run that only touched the
store and failed files nothing: undo would restore a half-state. A run that changed the world files its
effects whatever happened — the files are placed, the keys are set, and undo must be able to reach them.
`undo` reverts the newest entry's effects newest first through the UndoPort, puts its keys back and
forgets it; an effect that cannot be reverted is named, never silently dropped."""

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import TracebackType
from typing import ClassVar, Self

import msgspec

from e_taxis.adapters.ports import StorePort
from e_taxis.harness.models.error import JournalError, PrimitiveError
from e_taxis.harness.models.journal import Journal, JournalEffect
from e_taxis.harness.models.ports import UndoPort

##### DEFAULTS #####
PREFIX: str = "journal:"


##### TYPES #####
class StoreJournal:
    """Satisfies StorePort and RecorderPort; reads pass through, writes and effects are recorded, the run is
    filed on `__aexit__`. `world` reverts effects on undo."""

    name: ClassVar[str] = "journal"

    __slots__ = ("_command", "_depth", "_effects", "_inner", "_world", "_writes")

    def __init__(self, inner: StorePort, *, world: UndoPort, command: str, depth: int) -> None:
        self._inner = inner
        self._world = world
        self._command = command
        self._depth = depth
        self._writes: dict[str, bytes | None] = {}
        self._effects: list[JournalEffect] = []

    ##### PRIVATE METHODS #####

    async def _common_record(self, key: str) -> None:
        """Keep the value from before the run: a key written twice restores to its first state."""
        match key in self._writes:
            case False:
                self._writes[key] = await self._inner.get(key)
            case _:
                pass

    async def _commit_file(self) -> None:
        entry = Journal(
            id=f"{time.time_ns():020d}",
            command=self._command,
            at=datetime.now(UTC),
            writes=tuple(self._writes.items()),
            effects=tuple(self._effects),
        )
        await self._inner.set(f"{PREFIX}{entry.id}", msgspec.json.encode(entry))
        for stale in (await self._common_ids())[: -self._depth]:
            await self._inner.delete(f"{PREFIX}{stale}")

    async def _undo_effect(self, effect: JournalEffect) -> str | None:
        """None once reverted; the reason when the world refused."""
        try:
            await self._world.run(effect)
        except PrimitiveError as exc:
            return exc.message
        except OSError as exc:
            return str(exc)
        return None

    async def _common_ids(self) -> list[str]:
        """Entry ids, oldest first: the zero-padded clock makes lexical order the order of the runs."""
        return sorted([key.removeprefix(PREFIX) async for key in self._inner.keys(PREFIX)])

    ############################################################

    ##### PUBLIC #####

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        ### a failed store-only run changed the store partially at most: filing it would make undo restore a half-state;
        ### a run with effects changed the world, failed or not, and only a filed entry lets undo reach it.
        match (exc_type, bool(self._writes), bool(self._effects)):
            case (_, _, True) | (None, True, _):
                await self._commit_file()
            case _:
                pass

    async def get(self, key: str) -> bytes | None:
        return await self._inner.get(key)

    async def set(self, key: str, value: bytes) -> None:
        await self._common_record(key)
        await self._inner.set(key, value)

    async def delete(self, key: str) -> None:
        await self._common_record(key)
        await self._inner.delete(key)

    def keys(self, prefix: str = "") -> AsyncIterator[str]:
        return self._inner.keys(prefix)

    def record(self, *effects: JournalEffect) -> None:
        self._effects.extend(effects)

    async def entries(self) -> list[Journal]:
        """Every filed run, newest first."""
        ids = await self._common_ids()
        return [
            msgspec.json.decode(raw, type=Journal)
            for entry_id in reversed(ids)
            if (raw := await self._inner.get(f"{PREFIX}{entry_id}")) is not None
        ]

    async def undo(self) -> Journal:
        """Revert the newest run's effects, newest first, restore its keys, then forget the run. Undo is not journaled.

        Every effect is attempted; those the world refuses are named in a JournalError once the rest are back."""
        match next(iter(await self.entries()), None):
            case None:
                msg = "nothing to undo: the journal is empty"
                raise JournalError(msg)
            case last:
                refused = [reason for effect in reversed(last.effects) if (reason := await self._undo_effect(effect))]
                for key, before in last.writes:
                    await (self._inner.delete(key) if before is None else self._inner.set(key, before))
                await self._inner.delete(f"{PREFIX}{last.id}")
        match refused:
            case []:
                return last
            case _:
                msg = (
                    f"undid `{last.command}` but {len(refused)} change(s) could not be reverted: {' · '.join(refused)}"
                )
                raise JournalError(msg)
