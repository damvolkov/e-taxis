"""tests/unit/e_taxis/workflow/engine/executor: the DAG run — overlap, skip on red, errors as evidence, resume."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.engine.executor import DagExecutor, SubjectExecutor
from e_taxis.workflow.models.error import WorkflowError
from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.plane import Cadence, Guard, NodeCard, NodeSpec, Role, Scope
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


##### PLANES #####
CORPUS = NodeCard(role=Role.GATE, summary="c", scope=Scope.CORPUS)
SUBJECT = NodeCard(role=Role.GATE, summary="s")
SETTLED = NodeCard(role=Role.DECIDE, summary="d", guard=Guard.SETTLED)
WEEKLY = NodeCard(role=Role.MEASURE, summary="w", cadence=(Cadence.WEEKLY,))
PLANE = (
    NodeSpec(id="render", use="corpus", card=CORPUS),
    NodeSpec(id="law", use="subject", card=SUBJECT, depends=("render",)),
    NodeSpec(id="probe", use="weekly", card=WEEKLY, depends=("render",)),
    NodeSpec(id="needs", use="settled", card=SETTLED, depends=("law", "probe")),
    NodeSpec(id="gather", use="corpus", card=CORPUS, depends=("needs",)),
    NodeSpec(id="after", use="subject", card=SUBJECT, depends=("law",)),
)


async def test_executor_plane_fans_subjects_and_gates(
    plane_state: Callable[..., Any], scripted_plane: Callable[..., Any]
) -> None:
    node = scripted_plane({("law", "s1"): Status.FAIL}, SUBJECT)
    nodes = {"corpus": node, "subject": node, "weekly": node, "settled": node}
    seen: list[NodeRun] = []
    runs = await SubjectExecutor(nodes, 4, seen.append).run(await plane_state(*PLANE))
    got = {(run.node, run.subject): run.status for run in runs}
    assert got == {
        ("render", ""): Status.OK,
        ("law", "s1"): Status.FAIL,
        ("law", "s2"): Status.OK,
        ("probe", "s1"): Status.IDLE,
        ("probe", "s2"): Status.IDLE,
        ("needs", "s1"): Status.OK,
        ("needs", "s2"): Status.OK,
        ("gather", ""): Status.OK,
        ("after", "s1"): Status.SKIP,
        ("after", "s2"): Status.OK,
    }
    assert len(seen) == len(runs)
    assert ("probe", "s1") not in node.seen
    assert next(run for run in runs if run.node == "probe").reason == "not due at cadence commit"


async def test_executor_plane_error_is_evidence_and_rerun_pays_once(
    plane_state: Callable[..., Any], scripted_plane: Callable[..., Any]
) -> None:
    node = scripted_plane({}, SUBJECT)
    graph = (NodeSpec(id="boom", use="subject", card=SUBJECT), NodeSpec(id="ok", use="subject", card=SUBJECT))
    state = await plane_state(*graph, subjects=("s1",))
    first = await SubjectExecutor({"subject": node}, 2).run(state)
    assert {run.node: run.status for run in first} == {"boom": Status.ERROR, "ok": Status.OK}
    assert first[0].reason == "RuntimeError: kaput"
    await SubjectExecutor({"subject": node}, 2).run(state)
    assert node.seen.count(("ok", "s1")) == 1
    assert node.seen.count(("boom", "s1")) == 2
