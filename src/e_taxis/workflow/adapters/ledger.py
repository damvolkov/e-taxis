"""adapters.ledger: the run ledger as one JSON line per step run, fsynced as it lands.

The file is the truth; the index is a cache of it. Opening an existing ledger replays it, so a step whose inputs
did not move is not paid for twice."""

import os
from typing import TYPE_CHECKING, Final, Self

import anyio
import msgspec

from e_taxis.workflow.models.run import NodeRun

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
ENCODER: Final[msgspec.json.Encoder] = msgspec.json.Encoder()
DECODER: Final[msgspec.json.Decoder[NodeRun]] = msgspec.json.Decoder(NodeRun)


##### TYPES #####
class JsonlLedger:
    """Satisfies LedgerPort: append-only JSONL, indexed by (step, subject) in memory."""

    __slots__ = ("_index", "_path", "_runs")

    def __init__(self, path: Path, runs: tuple[NodeRun, ...] = ()) -> None:
        self._path = path
        self._runs = list(runs)
        self._index = {(run.node, run.subject): run for run in runs}

    ##### PRIVATE METHODS #####

    def _append_write(self, run: NodeRun) -> None:
        with self._path.open("ab") as sink:
            sink.write(ENCODER.encode(run) + b"\n")
            sink.flush()
            os.fsync(sink.fileno())

    ############################################################

    ##### PUBLIC #####

    @classmethod
    async def open(cls, path: Path) -> Self:
        """The ledger at `path`, replayed when it exists."""
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        found = await anyio.Path(path).exists()
        raw = await anyio.Path(path).read_bytes() if found else b""
        return cls(path, tuple(map(DECODER.decode, raw.splitlines())))

    async def append(self, run: NodeRun) -> None:
        """Durable first, visible second: a crash never leaves the index ahead of the file."""
        await anyio.to_thread.run_sync(self._append_write, run)
        self._runs.append(run)
        self._index[run.node, run.subject] = run

    def latest(self, node: str, subject: str = "") -> NodeRun | None:
        return self._index.get((node, subject))

    def runs(self) -> tuple[NodeRun, ...]:
        return tuple(self._runs)
