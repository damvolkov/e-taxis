"""sweep.ledger: what radar-field has already reported — state, never config (`TAXIS_RADAR_STATE/ledger.json`).

Per voice (the search agent's findings under `search`), every URL reported with the date it was first seen. The
ledger node reads it for the frame's voices only; report is the one writer, and a URL keeps its first date. The
file is replaced whole, never edited in place: a crash leaves the old ledger or the new one."""

from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import SEARCH, Frame, Seen

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


##### TYPES #####
class SweepLedger:
    """The seen ledger at `path`."""

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path

    ##### PRIVATE METHODS #####

    async def _common_load(self) -> Seen:
        try:
            raw = await anyio.Path(self._path).read_bytes()
        except FileNotFoundError:
            return Seen()
        try:
            return msgspec.json.decode(raw, type=Seen)
        except (msgspec.ValidationError, msgspec.DecodeError) as bad:
            msg = f"{self._path}: ledger.json does not fit its model: {bad}"
            raise SweepError(msg) from bad

    ############################################################

    ##### PUBLIC #####

    async def read(self, frame: Frame) -> Seen:
        """What was seen of the frame's voices, and of the open web."""
        wanted = {voice.id for voice in frame.voices} | {SEARCH}
        return Seen(seen={voice: urls for voice, urls in (await self._common_load()).seen.items() if voice in wanted})

    async def record(self, seen: Mapping[str, Mapping[str, str]]) -> int:
        """`seen` merged in, first dates kept; how many URLs it added."""
        held = (await self._common_load()).seen
        merged = {voice: {**seen.get(voice, {}), **held.get(voice, {})} for voice in held.keys() | seen.keys()}
        added = sum(len(urls) for urls in merged.values()) - sum(len(urls) for urls in held.values())
        await anyio.Path(self._path.parent).mkdir(parents=True, exist_ok=True)
        staged = anyio.Path(self._path.with_suffix(".tmp"))
        await staged.write_bytes(
            msgspec.json.format(msgspec.json.encode(Seen(seen=dict(sorted(merged.items())))), indent=2)
        )
        await staged.replace(self._path)
        return added
