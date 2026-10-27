"""tests/unit/e_taxis/workflow/adapters/sandbox: git around a plane run, on a real checkout — the clone, what moved,
the overlay of a folder or a file, the patch and its three-way apply."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.adapters.sandbox import GitSandbox

SPEC = "specs/tekton/claudecode.yaml"
SKILL = "core/tekton/skills/algo-py-core"


async def test_sandbox_open_is_reused(sandbox: GitSandbox, plane_nous: Path, tmp_path: Path) -> None:
    base = await sandbox.head(plane_nous)
    clone = await sandbox.open(plane_nous, tmp_path / "clone", base)
    (clone / "marker").write_text("kept\n")
    assert await sandbox.open(plane_nous, clone, base) == clone
    assert (clone / "marker").read_text() == "kept\n"
    assert await sandbox.head(clone) == base


async def test_sandbox_overlay_a_file_and_a_deletion(sandbox: GitSandbox, plane_nous: Path, tmp_path: Path) -> None:
    clone = await sandbox.open(plane_nous, tmp_path / "clone", await sandbox.head(plane_nous))
    (plane_nous / SPEC).write_text("spec: changed\n")
    await sandbox.overlay(plane_nous, clone, SPEC)
    assert (clone / SPEC).read_text() == "spec: changed\n"
    (plane_nous / SPEC).unlink()
    await sandbox.overlay(plane_nous, clone, SPEC)
    assert not (clone / SPEC).exists()
    assert await sandbox.dirty(clone, "specs") == (SPEC,)


async def test_sandbox_fingerprint_sees_a_deleted_file(sandbox: GitSandbox, plane_nous: Path) -> None:
    before, _ = await sandbox.fingerprint(plane_nous)
    (plane_nous / SPEC).unlink()
    after, hashes = await sandbox.fingerprint(plane_nous)
    assert before != after
    assert hashes == {SPEC: "absent"}


async def test_sandbox_diff_and_apply(sandbox: GitSandbox, plane_nous: Path, tmp_path: Path) -> None:
    base = await sandbox.head(plane_nous)
    clone = await sandbox.open(plane_nous, tmp_path / "clone", base)
    (clone / SKILL / "references" / "new.md").write_text("new\n")
    patch = tmp_path / "p.patch"
    patch.write_text(await sandbox.diff(clone, base, SKILL))
    assert await sandbox.changed(clone, base, SKILL) == (f"{SKILL}/references/new.md",)
    assert await sandbox.apply(plane_nous, patch, check=True)
    assert await sandbox.apply(plane_nous, patch)
    assert await sandbox.apply(plane_nous, patch, check=True, reverse=True)
    assert not await sandbox.apply(plane_nous, patch, check=True)
    await sandbox.close(clone)
    assert not clone.exists()
