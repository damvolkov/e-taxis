"""tests/unit/e_taxis/workflow/assess/inventory: the rows that name the candidate's needles, over a mini checkout and
two live trees (`tests/resources/assess`); past assessments kept whole."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.assess.inventory import AssessInventory
from e_taxis.workflow.models.assess import Candidate

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_resources import Resources


@pytest.fixture
def taker(resources: Resources) -> AssessInventory:
    root = resources.path / "assess"
    trees = (root / "trees" / "opencode", root / "trees" / "claude", root / "trees" / "absent")
    return AssessInventory(root / "nous", trees=trees, reports=root / "nous" / ".reports" / "workflows" / "soa-assess")


@pytest.mark.parametrize(
    ("candidate", "keywords", "names"),
    [
        (
            Candidate(tech="redis", name="redis", repo="redis/redis-py"),
            (),
            ["cashews", "valkey", "redis-mcp", "redis-cli"],
        ),
        (Candidate(tech="x", name="kg"), ("Knowledge Graph", " "), ["ml-py-rag"]),
        (Candidate(tech="x", name="nothing-here"), (), []),
    ],
    ids=["name-tokens", "keyword-phrase", "none"],
)
async def test_inventory_take(
    taker: AssessInventory, candidate: Candidate, keywords: tuple[str, ...], names: list[str]
) -> None:
    taken = await taker.take(candidate, keywords)
    assert [row.name for row in taken.rows] == names
    assert len(taken.assessed) == 1
    assert taken.assessed[0].startswith("valkey: adopt on 2026-10-01 (")


async def test_inventory_take_rows_say_where_and_what(taker: AssessInventory) -> None:
    rows = {row.name: row for row in (await taker.take(Candidate(tech="r", name="redis"), ())).rows}
    assert (rows["cashews"].where, rows["cashews"].role) == (
        "core/tekton/skills/data-py-cache/references/lib.md:5",
        "memory + Redis behind one API",
    )
    assert (rows["valkey"].where, rows["valkey"].role) == (
        "core/common/stack.yaml",
        "service: The open Redis fork, shared state",
    )
    assert rows["redis-mcp"].role == "mcp: uvx redis-mcp"
    assert rows["redis-cli"].role == "command: "


async def test_inventory_take_an_empty_checkout(tmp_path: Path) -> None:
    taken = await AssessInventory(tmp_path, trees=(), reports=tmp_path / "r").take(Candidate(tech="x", name="xyz"), ())
    assert (taken.rows, taken.assessed) == ((), ())
