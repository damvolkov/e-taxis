"""tests/unit/e_taxis/workflow/engine/chart: a declaration drawn as chains — exact parents, loops and conditions."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.engine.chart import WorkflowChart

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.models.workflow import Workflow

RUN = "true"


@pytest.mark.parametrize(
    ("nodes", "lines"),
    [
        (
            [
                {"id": "a", "run": RUN},
                {"id": "b", "depends": ["a"], "actor": "x"},
                {"id": "c", "depends": ["b"], "run": RUN},
            ],
            ["  D a → S b → D c"],
        ),
        (
            [
                {"id": "a", "run": RUN},
                {"id": "b", "depends": ["a"], "run": RUN},
                {"id": "c", "depends": ["a"], "run": RUN},
            ],
            ["  D a", "  D b   ← a", "  D c   ← a"],
        ),
        (
            [
                {"id": "a", "run": RUN},
                {"id": "b", "run": RUN},
                {"id": "c", "depends": ["a", "b"], "instruction": "lead"},
                {"id": "d", "depends": ["c"], "run": RUN},
            ],
            ["  D a", "  D b", "  S c → D d   ← a · b"],
        ),
    ],
    ids=["chain", "fan-out", "join"],
)
async def test_chart_lines(declare: Callable[..., Workflow], nodes: list[dict[str, object]], lines: list[str]) -> None:
    assert WorkflowChart(declare(nodes)).render().splitlines()[1:] == lines


async def test_chart_marks_loop_and_condition(declare: Callable[..., Workflow]) -> None:
    decl = declare(
        [
            {"id": "a", "run": RUN},
            {"id": "b", "depends": ["a"], "run": RUN, "when": {"go": ["yes", "maybe"]}},
        ],
        parameters={"go": "whether"},
        loop={"nodes": ["a"], "max": 3, "until": "a"},
    )
    assert WorkflowChart(decl).render().splitlines() == [
        "w — Draw it",
        "  params go",
        "  D a ↻3 → D b ?go=yes|maybe",
    ]


@pytest.mark.parametrize(
    ("description", "heading"),
    [
        ("One clause — then more", "w — One clause"),
        (" ".join(["word"] * 30), f"w — {' '.join(['word'] * 20)}…"),
    ],
    ids=["clause", "long"],
)
async def test_chart_heading(declare: Callable[..., Workflow], description: str, heading: str) -> None:
    decl = declare([{"id": "a", "run": RUN}], description=description)
    assert WorkflowChart(decl).render().splitlines()[0] == heading
