"""tests/unit/e_taxis/workflow/adapters/evals: the ledgers read at `core/tekton/evals/`, or at the legacy
`ops/evaluator/ledgers/` only when the checkout has no new home."""

import shutil
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.adapters.evals import NousEvals
from e_taxis.workflow.models.error import PlaneError

if TYPE_CHECKING:
    from pathlib import Path


async def test_evals_reads_the_new_home(plane_nous: Path) -> None:
    queries, where = await NousEvals().queries(plane_nous, "algo-py-core")
    tasks, there = await NousEvals().tasks(plane_nous, "algo-py-core")
    assert queries is not None
    assert tasks is not None
    assert (len(queries.cases), where) == (2, "core/tekton/evals/queries/algo-py-core.md")
    assert (len(tasks.tasks), there) == (3, "core/tekton/evals/tasks/algo-py-core.md")


async def test_evals_falls_back_to_the_legacy_ledgers(plane_nous: Path) -> None:
    legacy = plane_nous / "ops/evaluator/ledgers"
    legacy.parent.mkdir(parents=True)
    shutil.move(plane_nous / "core/tekton/evals", legacy)
    queries, where = await NousEvals().queries(plane_nous, "algo-py-core")
    assert queries is not None
    assert (len(queries.cases), where) == (2, "ops/evaluator/ledgers/queries/algo-py-core.md")


async def test_evals_missing_set_is_none(plane_nous: Path) -> None:
    assert await NousEvals().queries(plane_nous, "ghost") == (None, "core/tekton/evals/queries/ghost.md")
    assert await NousEvals().tasks(plane_nous, "ghost") == (None, "core/tekton/evals/tasks/ghost.md")


async def test_evals_set_without_block_is_refused(plane_nous: Path) -> None:
    (plane_nous / "core/tekton/evals/tasks/algo-py-core.md").write_text("# prose only\n")
    with pytest.raises(PlaneError, match="no ```toml block"):
        await NousEvals().tasks(plane_nous, "algo-py-core")
