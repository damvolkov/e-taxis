"""tests/unit/e_taxis/adapters/primitives/file: one marked block in a text file — inserted, replaced, removed, undone;
the text outside its markers is never touched."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.harness.models.journal import JournalBlock
from e_taxis.harness.models.ports import PrimitivePort

if TYPE_CHECKING:
    from pathlib import Path

WITH = {"file": "~/.claude/CLAUDE.md", "block": "memory", "text": "Remember things.\n"}
BLOCK = "<!-- e-taxis:memory -->\nRemember things.\n<!-- /e-taxis:memory -->\n"
REMOVAL = {"file": "~/.claude/CLAUDE.md", "block": "memory"}


@pytest.fixture
def claude_md(claude_dir: Path) -> Path:
    claude_dir.mkdir()
    return claude_dir / "CLAUDE.md"


async def test_file_satisfies_the_port(block) -> None:
    assert isinstance(block, PrimitivePort)


async def test_file_install_into_a_missing_file_and_its_undo(block, entry, ctx, undo, claude_dir: Path) -> None:
    part = entry("file", WITH)
    step = await block.install(part, part.recipe(ctx.target), ctx)
    assert (claude_dir / "CLAUDE.md").read_text() == BLOCK
    assert step.effects == (JournalBlock(file=str(claude_dir / "CLAUDE.md"), block="memory", before=None, fresh=True),)
    await undo(*step.effects)
    assert not (claude_dir / "CLAUDE.md").exists()


@pytest.mark.parametrize("text", ["# Persona\n\nBe terse.\n", "no trailing newline"], ids=["newline", "bare"])
async def test_file_install_appends_and_undo_restores_the_text(block, entry, ctx, undo, claude_md: Path, text) -> None:
    claude_md.write_text(text)
    part = entry("file", WITH)
    step = await block.install(part, part.recipe(ctx.target), ctx)
    assert claude_md.read_text() == text.rstrip("\n") + "\n\n" + BLOCK
    await undo(*step.effects)
    assert claude_md.read_text().rstrip("\n") == text.rstrip("\n")


async def test_file_install_is_idempotent(block, entry, ctx, claude_md: Path) -> None:
    part = entry("file", WITH)
    await block.install(part, part.recipe(ctx.target), ctx)
    once = claude_md.read_text()
    assert (await block.install(part, part.recipe(ctx.target), ctx)).effects == ()
    assert claude_md.read_text() == once


async def test_file_install_replaces_only_the_body(block, entry, ctx, undo, claude_md: Path) -> None:
    claude_md.write_text(f"head\n\n{BLOCK.replace('Remember things.', 'old body')}tail\n")
    part = entry("file", WITH)
    step = await block.install(part, part.recipe(ctx.target), ctx)
    assert claude_md.read_text() == f"head\n\n{BLOCK}tail\n"
    await undo(*step.effects)
    assert claude_md.read_text() == f"head\n\n{BLOCK.replace('Remember things.', 'old body')}tail\n"


async def test_file_uninstall_removes_the_block_and_its_undo(block, entry, ctx, undo, claude_md: Path) -> None:
    claude_md.write_text(f"# Persona\n\n{BLOCK}")
    part = entry("file", WITH, uninstall=REMOVAL)
    step = await block.uninstall(part, part.uninstall, ctx)
    assert claude_md.read_text() == "# Persona\n"
    await undo(*step.effects)
    assert claude_md.read_text() == f"# Persona\n\n{BLOCK}"


async def test_file_uninstall_without_the_block_changes_nothing(block, entry, ctx, claude_md: Path) -> None:
    claude_md.write_text("# Persona\n")
    part = entry("file", WITH, uninstall=REMOVAL)
    assert (await block.uninstall(part, part.uninstall, ctx)).effects == ()
    assert claude_md.read_text() == "# Persona\n"


async def test_file_undo_of_a_vanished_block_changes_nothing(block, entry, ctx, undo, claude_md: Path) -> None:
    claude_md.write_text("# Persona\n")
    part = entry("file", WITH)
    effects = (await block.install(part, part.recipe(ctx.target), ctx)).effects
    claude_md.write_text("# Rewritten\n")
    await undo(*effects)
    assert claude_md.read_text() == "# Rewritten\n"


async def test_file_uninstall_between_paragraphs_keeps_one_blank_line(block, entry, ctx, claude_md: Path) -> None:
    claude_md.write_text(f"head\n\n{BLOCK}tail\n")
    part = entry("file", WITH, uninstall=REMOVAL)
    await block.uninstall(part, part.uninstall, ctx)
    assert claude_md.read_text() == "head\n\ntail\n"
