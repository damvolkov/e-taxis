"""tests/unit/e_taxis/workflow/commands: checkouts in the state a promotion meets — an enhancement with a patch, and the
same with HEAD moved past its base."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

LIB = "core/tekton/skills/algo-py-core/references/lib.md"


@pytest.fixture
def enhanced(taxis: Callable[..., tuple[int, str, str]], plane_nous: Path, plane_deps: PlaneRun) -> Path:
    """An enhancement of the mini checkout's skill over a hand edit, the edit then undone: a patch to promote."""
    lib = plane_nous / LIB
    original = lib.read_text()
    lib.write_text(original + "\nPromoted depth.\n")
    code, _, _ = taxis("enhance", "run", "skill", "algo-py-core", "--nous", str(plane_nous), "--manual")
    lib.write_text(original)
    assert code == 0
    return plane_nous


@pytest.fixture
async def moved(enhanced: Path, tree, commit: Callable[..., Awaitable[str]]) -> Path:
    """The enhanced checkout with one commit past the run's base."""
    tree(enhanced, {"NEW.md": "moved\n"})
    await commit(enhanced, "moved")
    return enhanced
