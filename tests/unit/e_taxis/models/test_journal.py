"""tests/unit/e_taxis/models/journal: a run's world effects round-trip through JSON, each tagged with its kind."""

from datetime import UTC, datetime

import msgspec

from e_taxis.models.journal import Journal, JournalBlock, JournalCommand, JournalFile, JournalKey


async def test_journal_effects_round_trip_tagged() -> None:
    effects = (
        JournalFile(path="/b", before=b"\x00\x01", mode=0o755),
        JournalKey(file="/s.json", path=("env", "K"), before=None, created=2, fresh=True),
        JournalBlock(file="/c.md", block="b", before="old"),
        JournalCommand(argv=("uv", "tool", "install", "x"), undo=("uv", "tool", "uninstall", "x")),
    )
    at = datetime(2026, 10, 15, tzinfo=UTC)
    raw = msgspec.json.encode(Journal(id="1", command="apply", at=at, writes=(), effects=effects))
    assert msgspec.json.decode(raw, type=Journal).effects == effects
    assert [effect["kind"] for effect in msgspec.json.decode(raw)["effects"]] == ["file", "key", "block", "command"]


async def test_journal_p1_entry_decodes_without_effects() -> None:
    raw = b'{"id":"1","command":"x","at":"2026-10-15T00:00:00Z","writes":[["k",null]]}'
    assert msgspec.json.decode(raw, type=Journal).effects == ()
