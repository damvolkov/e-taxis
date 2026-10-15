"""tests/unit/e_taxis/runtime/journal: the StorePort decorator — first value kept, clean exits filed, depth bounded."""

import pytest

from adapters.ports import StorePort
from e_taxis.adapters.ports import RecorderPort
from e_taxis.models.error import JournalError
from e_taxis.models.journal import JournalCommand, JournalFile, JournalKey
from e_taxis.runtime.journal import PREFIX, StoreJournal

PLACED = JournalFile(path="/bin/x", before=None)
KEYED = JournalKey(file="/s.json", path=("env", "A"), created=2)
REGISTERED = JournalCommand(argv=("uv", "tool", "install", "x"), undo=("uv", "tool", "uninstall", "x"))


def test_journal_satisfies_the_store_and_recorder_ports(store, undoer) -> None:
    journal = StoreJournal(store, world=undoer, command="x", depth=5)
    assert isinstance(journal, StorePort)
    assert isinstance(journal, RecorderPort)


async def test_journal_undo_restores_the_value_before_the_first_write(store, undoer) -> None:
    store.data["k"] = b"orig"
    async with StoreJournal(store, world=undoer, command="edit", depth=5) as journal:
        await journal.set("k", b"one")
        await journal.set("k", b"two")
        await journal.set("new", b"x")
    entry = await StoreJournal(store, world=undoer, command="undo", depth=5).undo()
    assert entry.command == "edit"
    assert store.data == {"k": b"orig"}


async def test_journal_undo_of_a_delete_brings_the_key_back(store, undoer) -> None:
    store.data["k"] = b"orig"
    async with StoreJournal(store, world=undoer, command="rm", depth=5) as journal:
        await journal.delete("k")
    await StoreJournal(store, world=undoer, command="undo", depth=5).undo()
    assert store.data["k"] == b"orig"


async def test_journal_files_nothing_when_the_run_fails(store, undoer) -> None:
    journal = StoreJournal(store, world=undoer, command="boom", depth=5)
    await journal.set("k", b"v")
    await journal.__aexit__(RuntimeError, RuntimeError(), None)
    assert not [key async for key in store.keys(PREFIX)]


async def test_journal_files_nothing_for_a_read_only_run(store, undoer) -> None:
    async with StoreJournal(store, world=undoer, command="read", depth=5) as journal:
        await journal.get("k")
        assert [key async for key in journal.keys("any")] == []
    assert await StoreJournal(store, world=undoer, command="list", depth=5).entries() == []


async def test_journal_keeps_only_the_newest_depth_runs(store, undoer) -> None:
    for step in range(3):
        async with StoreJournal(store, world=undoer, command=f"run {step}", depth=2) as journal:
            await journal.set("k", str(step).encode())
    entries = await StoreJournal(store, world=undoer, command="list", depth=2).entries()
    assert [entry.command for entry in entries] == ["run 2", "run 1"]


async def test_journal_undo_on_empty_is_refused(store, undoer) -> None:
    with pytest.raises(JournalError, match="nothing to undo"):
        await StoreJournal(store, world=undoer, command="undo", depth=5).undo()


async def test_journal_undo_reverts_effects_newest_first(store, undoer) -> None:
    async with StoreJournal(store, world=undoer, command="apply", depth=5) as journal:
        journal.record(PLACED, KEYED)
        journal.record(REGISTERED)
    entry = await StoreJournal(store, world=undoer, command="undo", depth=5).undo()
    assert (entry.effects, undoer.reverted) == ((PLACED, KEYED, REGISTERED), [REGISTERED, KEYED, PLACED])
    assert await StoreJournal(store, world=undoer, command="list", depth=5).entries() == []


async def test_journal_files_effects_even_when_the_run_fails(store, undoer) -> None:
    journal = StoreJournal(store, world=undoer, command="apply", depth=5)
    journal.record(PLACED)
    await journal.__aexit__(RuntimeError, RuntimeError(), None)
    assert [entry.effects for entry in await journal.entries()] == [(PLACED,)]


async def test_journal_undo_reverts_what_it_can_and_names_the_rest(store, undoer) -> None:
    undoer.failing.append(KEYED)
    async with StoreJournal(store, world=undoer, command="apply", depth=5) as journal:
        journal.record(PLACED, KEYED)
    with pytest.raises(JournalError, match=r"undid `apply` but 1 change\(s\) could not be reverted: cannot revert"):
        await StoreJournal(store, world=undoer, command="undo", depth=5).undo()
    assert undoer.reverted == [PLACED]
    assert await StoreJournal(store, world=undoer, command="list", depth=5).entries() == []


async def test_journal_undo_names_a_filesystem_refusal(store, undoer) -> None:
    undoer.failing.append(PLACED)
    undoer.oserror = True
    async with StoreJournal(store, world=undoer, command="apply", depth=5) as journal:
        journal.record(PLACED)
    with pytest.raises(JournalError, match="Permission denied"):
        await StoreJournal(store, world=undoer, command="undo", depth=5).undo()
