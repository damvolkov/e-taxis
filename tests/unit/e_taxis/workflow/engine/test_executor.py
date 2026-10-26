"""tests/unit/e_taxis/workflow/engine/executor: the DAG run — overlap, skip on red, errors as evidence, resume."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.engine.executor import DagExecutor
from e_taxis.workflow.models.error import WorkflowError
from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.run import NodeRun, Status

if TYPE_CHECKING:
    from collections.abc import Callable


GRAPH = (
    StepSpec(id="a", run="x"),
    StepSpec(id="b", depends=("a",), run="x"),
    StepSpec(id="c", depends=("a",), run="x"),
    StepSpec(id="d", depends=("b", "c"), run="x"),
)


async def test_executor_runs_in_dependency_order_with_overlap(
    state: Callable[..., Any], scripted: Callable[..., Any]
) -> None:
    node, seen = scripted({}), []
    runs = await DagExecutor(node, 4, seen.append).run(await state(*GRAPH))
    assert [run.node for run in runs] == ["a", "b", "c", "d"]
    assert node.order[0] == "a"
    assert node.order[-1] == "d"
    assert node.peak == 2
    assert sorted(run.node for run in seen) == sorted(node.order)


async def test_executor_bounds_concurrency(state: Callable[..., Any], scripted: Callable[..., Any]) -> None:
    node = scripted({})
    await DagExecutor(node, 1).run(await state(*GRAPH))
    assert node.peak == 1


async def test_executor_red_upstream_skips_downstream(state: Callable[..., Any], scripted: Callable[..., Any]) -> None:
    runs = await DagExecutor(scripted({"b": Status.FAIL}), 4).run(await state(*GRAPH))
    by = {run.node: run for run in runs}
    assert (by["c"].status, by["d"].status) == (Status.OK, Status.SKIP)
    assert by["d"].reason == "upstream b is fail"


async def test_executor_exception_is_an_error_not_a_crash(
    state: Callable[..., Any], scripted: Callable[..., Any]
) -> None:
    graph = (StepSpec(id="boom", run="x"), StepSpec(id="after", depends=("boom",), run="x"))
    runs = await DagExecutor(scripted({}), 4).run(await state(*graph))
    assert [(run.status, run.reason) for run in runs] == [
        (Status.ERROR, "RuntimeError: kaput"),
        (Status.SKIP, "upstream boom is error"),
    ]


async def test_executor_refuses_a_cycle(state: Callable[..., Any], scripted: Callable[..., Any]) -> None:
    graph = (StepSpec(id="a", depends=("b",), run="x"), StepSpec(id="b", depends=("a",), run="x"))
    with pytest.raises(WorkflowError, match="cycle through"):
        await DagExecutor(scripted({}), 4).run(await state(*graph))


async def test_executor_resume_keeps_what_did_not_move(state: Callable[..., Any], scripted: Callable[..., Any]) -> None:
    first = await state(*GRAPH)
    await DagExecutor(scripted({"d": Status.ERROR}), 4).run(first)
    node = scripted({})
    runs = await DagExecutor(node, 4).run(first)
    assert node.order == ["d"]
    assert all(isinstance(run, NodeRun) for run in runs)
    assert [run.status for run in runs] == [Status.OK] * 4
