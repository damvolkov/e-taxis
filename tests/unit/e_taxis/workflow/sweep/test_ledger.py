"""tests/unit/e_taxis/workflow/sweep/ledger: the seen ledger — read for a frame's voices, appended to by report only."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import Frame, Seen, Voice, VoiceKind
from e_taxis.workflow.sweep.ledger import SweepLedger

if TYPE_CHECKING:
    from pathlib import Path

FRAME = Frame(
    brief="b",
    topic="",
    keywords=(),
    since="2026-10-26",
    until="2026-10-28",
    voices=(Voice(id="ada", url="https://www.linkedin.com/in/adavoice", kind=VoiceKind.LINKEDIN_PROFILE),),
)


async def test_ledger_read_without_a_file_is_empty(tmp_path: Path) -> None:
    assert await SweepLedger(tmp_path / "radar" / "ledger.json").read(FRAME) == Seen()


async def test_ledger_read_keeps_the_frames_voices_and_search(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    held = {"ada": {"https://a/1": "2026-10-01"}, "search": {"https://s/1": "2026-10-02"}, "gone": {"https://g": "x"}}
    path.write_bytes(msgspec.json.encode(Seen(seen=held)))
    assert (await SweepLedger(path).read(FRAME)).seen == {"ada": held["ada"], "search": held["search"]}


async def test_ledger_read_refuses_a_broken_file(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text("{not json")
    with pytest.raises(SweepError, match=r"ledger\.json does not fit"):
        await SweepLedger(path).read(FRAME)


async def test_ledger_record_keeps_the_first_date(tmp_path: Path) -> None:
    ledger = SweepLedger(tmp_path / "state" / "ledger.json")
    assert await ledger.record({"ada": {"https://a/1": "2026-10-01"}}) == 1
    assert await ledger.record({"ada": {"https://a/1": "2026-10-28", "https://a/2": "2026-10-28"}, "search": {}}) == 1
    assert (await ledger.read(FRAME)).seen == {
        "ada": {"https://a/1": "2026-10-01", "https://a/2": "2026-10-28"},
        "search": {},
    }
