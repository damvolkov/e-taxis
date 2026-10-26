"""Unit tests for the corpus store: snapshot, detect, restore, release.

The store is the only piece that touches git. Everything asserted here is observable
on disk or in the store's own values — never a call it made.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from ops.models.history import Retention
from ops.transpiler.history.store import Store, StoreError
from tests.unit.ops.transpiler.history.conftest import CORPUS, write


# ----------------------------------------------------------------- existence
def test_store_is_not_ready_before_it_is_initialised(tree: Path, tmp_path: Path) -> None:
    assert not Store(tree, tmp_path / "absent.git").ready()


def test_store_is_ready_once_initialised(store: Store) -> None:
    assert store.ready()


def test_store_keeps_its_git_dir_out_of_the_tree(store: Store, tree: Path) -> None:
    """Nothing that writes into the config dir may see, index or corrupt the history."""
    assert not (tree / ".git").exists()
    assert store.git_dir.is_dir()


def test_store_initialise_is_idempotent(store: Store) -> None:
    store.initialise()
    assert store.ready()


def test_store_refuses_to_act_before_initialisation(tree: Path, tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="not initialised"):
        Store(tree, tmp_path / "absent.git").snapshot("manual")


# ------------------------------------------------------------------ snapshot
def test_first_snapshot_records_the_whole_corpus(store: Store) -> None:
    snapshot = store.snapshot("export")
    assert snapshot is not None
    assert snapshot.commit
    assert snapshot.reason == "export"


def test_snapshot_timestamp_is_timezone_aware(store: Store) -> None:
    snapshot = store.snapshot("export")
    assert snapshot is not None and snapshot.at.tzinfo is not None


def test_snapshot_without_changes_records_nothing(store: Store) -> None:
    """An export that changed nothing must not leave a hollow recovery point."""
    store.snapshot("export")
    assert store.snapshot("export") is None


def test_snapshot_carries_its_note(store: Store) -> None:
    snapshot = store.snapshot("pre-export", note="before the transpile")
    assert snapshot is not None and snapshot.note == "before the transpile"


# --------------------------------------------------------------- what moved
def test_changed_lists_nothing_on_a_clean_tree(store: Store) -> None:
    store.snapshot("export")
    assert store.changed() == ()


def test_changed_names_an_added_path(store: Store, tree: Path) -> None:
    store.snapshot("export")
    write(tree, {"agents/scout.md": "new\n"})
    assert [(c.path, c.kind) for c in store.changed()] == [("agents/scout.md", "added")]


def test_changed_names_a_modified_path(store: Store, tree: Path) -> None:
    store.snapshot("export")
    write(tree, {"skills/data-py-cache/SKILL.md": "# data-py-cache\n\nrule one, rewritten\n"})
    assert [(c.path, c.kind) for c in store.changed()] == [("skills/data-py-cache/SKILL.md", "changed")]


def test_changed_names_a_removed_path(store: Store, tree: Path) -> None:
    store.snapshot("export")
    (tree / "agents/builder.md").unlink()
    assert [(c.path, c.kind) for c in store.changed()] == [("agents/builder.md", "removed")]


def test_changed_ignores_what_the_runtime_owns(store: Store, tree: Path) -> None:
    """Sessions and runtime-owned skill trees share the directory; they are not the corpus."""
    store.snapshot("export")
    write(tree, {"sessions/live.json": '{"open": false}', "skills/synced/ghost/SKILL.md": "edited"})
    assert store.changed() == ()


# -------------------------------------------------------- live vs a point
def test_pending_without_a_pointer_is_the_work_tree_against_the_head(store: Store, tree: Path) -> None:
    """The `diff` no-arg case: live vs the newest point must read exactly like `changed`."""
    store.snapshot("export")
    write(tree, {"agents/scout.md": "new\n", "AGENTS.md": "# rewritten\n"})
    assert store.pending() == store.changed()


def test_pending_against_a_named_point_catches_modified_and_new(store: Store, tree: Path) -> None:
    """`git diff <point>` misses a never-committed file; the merge with status carries it."""
    base = store.snapshot("export")
    assert base is not None
    write(tree, {"skills/data-py-cache/SKILL.md": "# data-py-cache\n\nchanged since base\n"})
    write(tree, {"commands/go.md": "new command\n"})
    found = {(c.path, c.kind) for c in store.pending(base.commit)}
    assert found == {("skills/data-py-cache/SKILL.md", "changed"), ("commands/go.md", "added")}


def test_pending_is_empty_when_live_matches_the_point(store: Store) -> None:
    base = store.snapshot("export")
    assert base is not None and store.pending(base.commit) == ()


# ------------------------------------------------------------ resolve
def test_resolve_accepts_a_commit_prefix(store: Store) -> None:
    base = store.snapshot("export")
    assert base is not None and store.resolve(base.commit[:8]).commit == base.commit


def test_resolve_accepts_the_ref_tail(store: Store) -> None:
    """The timestamp that names the ref is a pointer too — no need to retype the commit."""
    base = store.snapshot("export")
    assert base is not None
    assert store.resolve(base.ref.rsplit("/", 1)[-1]).commit == base.commit


def test_resolve_refuses_an_unknown_token(store: Store) -> None:
    store.snapshot("export")
    with pytest.raises(StoreError):
        store.resolve("deadbeef")


# -------------------------------------------------------------- restoration
def test_restore_brings_back_a_removed_file(store: Store, tree: Path) -> None:
    snapshot = store.snapshot("export")
    (tree / "agents/builder.md").unlink()
    assert snapshot is not None
    store.restore(snapshot.commit)
    assert (tree / "agents/builder.md").read_text() == CORPUS["agents/builder.md"]


def test_restore_reverts_a_modified_file(store: Store, tree: Path) -> None:
    snapshot = store.snapshot("export")
    write(tree, {"AGENTS.md": "# someone else\n"})
    assert snapshot is not None
    store.restore(snapshot.commit)
    assert (tree / "AGENTS.md").read_text() == CORPUS["AGENTS.md"]


def test_restore_removes_a_file_the_snapshot_never_held(store: Store, tree: Path) -> None:
    snapshot = store.snapshot("export")
    write(tree, {"agents/intruder.md": "not in the snapshot\n"})
    assert snapshot is not None
    store.restore(snapshot.commit)
    assert not (tree / "agents/intruder.md").exists()


def test_restore_leaves_the_tree_clean(store: Store, tree: Path) -> None:
    snapshot = store.snapshot("export")
    write(tree, {"AGENTS.md": "drift\n", "agents/intruder.md": "drift\n"})
    (tree / "agents/builder.md").unlink()
    assert snapshot is not None
    store.restore(snapshot.commit)
    assert store.changed() == ()


def test_restore_spares_what_the_runtime_owns(store: Store, tree: Path) -> None:
    """A regression of the corpus must not take the live session with it."""
    snapshot = store.snapshot("export")
    write(tree, {"sessions/live.json": '{"open": "still"}'})
    assert snapshot is not None
    store.restore(snapshot.commit)
    assert (tree / "sessions/live.json").read_text() == '{"open": "still"}'


def test_restore_to_an_unknown_commit_fails_loudly(store: Store) -> None:
    store.snapshot("export")
    with pytest.raises(StoreError):
        store.restore("0" * 40)


# ------------------------------------------------------------------ history
def test_log_is_newest_first(store: Store, tree: Path) -> None:
    first = store.snapshot("export")
    write(tree, {"AGENTS.md": "# second\n"})
    second = store.snapshot("export")
    assert first is not None and second is not None
    assert [s.commit for s in store.log()] == [second.commit, first.commit]


def test_head_is_the_last_snapshot(store: Store, tree: Path) -> None:
    store.snapshot("export")
    write(tree, {"AGENTS.md": "# second\n"})
    latest = store.snapshot("export")
    head = store.head()
    assert latest is not None and head is not None and head.commit == latest.commit


def test_head_is_none_on_an_empty_store(store: Store) -> None:
    assert store.head() is None


def test_log_preserves_the_reason_of_each_snapshot(store: Store, tree: Path) -> None:
    store.snapshot("pre-export")
    write(tree, {"AGENTS.md": "# second\n"})
    store.snapshot("export")
    assert [s.reason for s in store.log()] == ["export", "pre-export"]


# ---------------------------------------------------------------- retention
def test_prune_keeps_every_point_inside_the_policy(store: Store, tree: Path) -> None:
    for index in range(3):
        write(tree, {"AGENTS.md": f"# {index}\n"})
        store.snapshot("export")
    assert store.prune(Retention(keep_last=10, keep_days=90)) == ()
    assert len(store.log()) == 3


def test_prune_releases_points_beyond_both_rules(store: Store, tree: Path) -> None:
    """Beyond the count *and* beyond the window: either rule alone protects a point."""
    for index in range(4):
        write(tree, {"AGENTS.md": f"# {index}\n"})
        store.snapshot("export")
    released = store.prune(Retention(keep_last=2, keep_days=0), now=dt.datetime.now(dt.UTC) + dt.timedelta(days=1))
    assert len(released) == 2
    assert len(store.log()) == 2


def test_prune_never_releases_the_head(store: Store, tree: Path) -> None:
    for index in range(3):
        write(tree, {"AGENTS.md": f"# {index}\n"})
        store.snapshot("export")
    head = store.head()
    store.prune(Retention(keep_last=0, keep_days=0), now=dt.datetime.now(dt.UTC) + dt.timedelta(days=1))
    after = store.head()
    assert head is not None and after is not None and after.commit == head.commit


# ------------------------------------------------------------------- specs
@pytest.fixture
def specs(tmp_path: Path) -> Path:
    """A specs folder beside the corpus, the way the repo holds it."""
    folder = tmp_path / "repo" / "specs"
    write(folder, {"opencode/config.yaml": "release: '2026.09.23'\n", "opencode/agent.yaml": "entity: agent\n"})
    return folder


def test_specs_are_none_before_the_head_is_sealed(store: Store, specs: Path) -> None:
    store.snapshot("manual")
    assert store.specs(specs) is None


def test_specs_are_empty_right_after_sealing(store: Store, specs: Path) -> None:
    store.snapshot("manual")
    store.seal(specs)
    assert store.specs(specs) == ()


def test_specs_name_what_moved_since_the_seal(store: Store, specs: Path) -> None:
    store.snapshot("manual")
    store.seal(specs)
    write(specs, {"opencode/config.yaml": "release: '2026.10.01'\n", "opencode/tools.yaml": "entity: tool\n"})
    (specs / "opencode" / "agent.yaml").unlink()
    assert {(c.path, c.kind) for c in store.specs(specs) or ()} == {
        ("specs/opencode/config.yaml", "changed"),
        ("specs/opencode/tools.yaml", "added"),
        ("specs/opencode/agent.yaml", "removed"),
    }


def test_seal_writes_nothing_into_the_repo(store: Store, specs: Path) -> None:
    store.snapshot("manual")
    before = sorted(p.relative_to(specs.parent) for p in specs.parent.rglob("*"))
    store.seal(specs)
    assert sorted(p.relative_to(specs.parent) for p in specs.parent.rglob("*")) == before


def test_seal_refuses_an_empty_store(store: Store, specs: Path) -> None:
    with pytest.raises(StoreError, match="no snapshot"):
        store.seal(specs)


def test_prune_releases_the_seal_with_its_point(store: Store, tree: Path, specs: Path) -> None:
    store.snapshot("manual")
    store.seal(specs)
    write(tree, {"AGENTS.md": "# moved\n"})
    store.snapshot("manual")
    store.prune(Retention(keep_last=1, keep_days=0), now=dt.datetime.now(dt.UTC) + dt.timedelta(days=1))
    assert store._git("for-each-ref", "refs/specs").strip() == ""
