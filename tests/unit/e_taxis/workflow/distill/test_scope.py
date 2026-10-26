"""tests/unit/e_taxis/workflow/distill/scope: guard, intake and the run's changed files — git, committed work only.

Defect 2: scan reported the working tree's changes (and the code graph's paged list), not the run's range. The range
is now `base...head` of the scope's branches: committed files only, every one of them, nothing uncommitted.
A commit with an empty body used to vanish from intake: its trailing separator is whitespace to `str.strip`."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.distill.scope import DistillScope
from e_taxis.workflow.models.distill import FileKind, Scope
from e_taxis.workflow.models.error import NothingError

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.adapters.command import ShellCommand


async def test_scope_guard_and_intake(command: ShellCommand, repo: Path) -> None:
    scope = await DistillScope(command).guard(repo, (), "", "made x faster")
    manifest = await DistillScope(command).intake(scope)
    assert scope.branches == ("feat/x",)
    assert scope.graph.endswith("-proj")
    assert scope.work == "made x faster"
    assert [c.subject for c in manifest.commits] == ["docs: notes", "feat: faster x"]
    assert manifest.commits[1].body == "measured 2x"
    assert {(f.path, f.kind) for f in manifest.files} == {
        ("a.py", FileKind.CODE),
        ("conf.yaml", FileKind.STRUCTURED),
        ("docs/notes.md", FileKind.DOCS),
        ("logo.png", FileKind.CODE),
    }


async def test_scope_changed_is_the_committed_range(command: ShellCommand, repo: Path, git) -> None:
    scope = await DistillScope(command).guard(repo, ("feat/x",), "main", "")
    await git(repo, "switch", "-q", "main")
    assert await DistillScope(command).changed(scope) == ("a.py", "conf.yaml", "docs/notes.md", "logo.png")


async def test_scope_guard_since_resolves_to_a_commit(command: ShellCommand, repo: Path, git) -> None:
    scope = await DistillScope(command).guard(repo, (), "main", "")
    assert scope.base == (await git(repo, "rev-parse", "main")).strip()


async def test_scope_guard_nothing_past_the_base(command: ShellCommand, repo: Path, git) -> None:
    await git(repo, "switch", "-q", "main")
    with pytest.raises(NothingError, match="no commit past") as nothing:
        await DistillScope(command).guard(repo, (), "", "")
    assert nothing.value.exit_code == 3


async def test_scope_guard_refuses_a_non_repository(command: ShellCommand, tmp_path: Path) -> None:
    with pytest.raises(NothingError, match="is not a git repository"):
        await DistillScope(command).guard(tmp_path, (), "", "")


async def test_scope_intake_skips_a_malformed_stat_line(fake_command) -> None:
    fake_command.answers[("git", "-C", "/p", "diff")] = "1\t2\ta.py\nbroken line\n-\t-\tlogo.png\n"
    manifest = await DistillScope(fake_command).intake(Scope(project="/p", graph="p", branches=("b",), base="x"))
    assert [(f.path, f.added, f.removed) for f in manifest.files] == [("a.py", 1, 2), ("logo.png", 0, 0)]
