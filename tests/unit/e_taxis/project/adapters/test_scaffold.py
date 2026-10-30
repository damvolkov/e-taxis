from typing import TYPE_CHECKING

from e_taxis.project.adapters.scaffold import Scaffold
from e_taxis.project.core.plan import Plan, PruneTexts
from e_taxis.project.models.manifest import Prune

if TYPE_CHECKING:
    from pathlib import Path


async def test_apply_prune_texts_missing_file(repo: Path, tmp_path: Path) -> None:
    """A rule shared across templates names a file this one never had: nothing to rewrite, nothing to fail."""
    plan = Plan(
        name="x", package="e_x", brand="e-x", actions=(PruneTexts(prunes=(Prune(file="compose.yml", pattern="a"),)),)
    )
    dest = Scaffold(repo).apply(plan, tmp_path / "out")
    assert not (dest / "compose.yml").exists()
