"""tests/unit/e_taxis/workflow/engine/reader: workflows read from an e-nous tree as executor graphs."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.reader import PlaneReader, WorkflowReader
from e_taxis.workflow.models.error import PlaneError, WorkflowError
from e_taxis.workflow.models.plane import NodeCard, NodeUse, Plane, PlaneDecl, Role, Target

if TYPE_CHECKING:
    from pathlib import Path


async def test_reader_ids_are_every_workflow_folder(reader: WorkflowReader) -> None:
    assert reader.ids() == ("broken", "demo", "looped", "reverse-distill", "soa-assess")


async def test_reader_steps_carry_what_runs_them(reader: WorkflowReader) -> None:
    graph, decl = reader.read("demo")
    assert [step.id for step in graph] == ["first", "echo", "think", "last"]
    assert (graph["think"].semantic, graph["think"].readonly, graph["think"].steps) == (True, True, 4)
    assert (graph["last"].when, graph["echo"].semantic) == ({"apply": ("true",)}, False)
    assert graph.summary.startswith("Every kind of step")
    assert decl.triggers[0].cli == "taxis workflow run demo"


async def test_reader_refuses_an_unknown_agent(reader: WorkflowReader) -> None:
    with pytest.raises(WorkflowError, match="unknown agent nobody"):
        reader.read("broken")


async def test_reader_refuses_an_unknown_id(reader: WorkflowReader) -> None:
    with pytest.raises(WorkflowError, match="no workflow 'missing'"):
        reader.read("missing")


async def test_reader_refuses_an_off_model_manifest(nous: Path) -> None:
    (nous / "core/tekton/workflows/demo/nodes/echo.yaml").write_text("id: echo\nrun: x\ntools: [grep]\n")
    with pytest.raises(WorkflowError, match="unknown field"):
        WorkflowReader(await GitNous(nous, None).load()).read("demo")


async def test_reader_port_without_schema_is_a_problem(nous: Path) -> None:
    (nous / "core/tekton/workflows/demo/schemas/Value.json").unlink()
    with pytest.raises(WorkflowError, match="names model Value, which has no schema"):
        WorkflowReader(await GitNous(nous, None).load()).read("demo")


async def test_reader_loop_unrolls_into_bounded_copies(reader: WorkflowReader) -> None:
    graph, _ = reader.read("looped")
    assert [step.id for step in graph] == [
        "start",
        "work_1",
        "check_1",
        "after_1",
        "work_2",
        "check_2",
        "after_2",
        "work_3",
        "check_3",
        "after_3",
        "report",
    ]
    assert (graph["work_2"].depends, graph["report"].depends) == (("start", "after_1"), ("after_3",))
    assert (graph["check_2"].until, graph["check_2"].previous, graph["check_1"].previous) == (True, "check_1", "")
    assert (graph["after_1"].closers, graph["work_2"].closers) == (("check_1",), ("check_1",))
    assert (graph["after_3"].closers, graph["work_3"].iteration) == (("check_1", "check_2", "check_3"), 3)


async def test_reader_bind_refuses_undeclared_and_defaults_the_rest(reader: WorkflowReader) -> None:
    _, decl = reader.read("demo")
    with pytest.raises(WorkflowError, match="undeclared parameter"):
        reader.bind(decl, {"nope": "x"})
    assert reader.bind(decl, {"value": "v"}) == {"value": "v", "apply": ""}


##### PLANES #####
CARD = NodeCard(role=Role.GATE, summary="g")


@pytest.mark.parametrize(
    ("nodes", "problem"),
    [
        ((NodeUse(use="ghost"),), "no node 'ghost'"),
        ((NodeUse(use="a"), NodeUse(use="a")), "duplicate id a"),
        ((NodeUse(use="a", depends=("z",)),), "a depends on unknown z"),
        ((NodeUse(use="a", depends=("b",)), NodeUse(use="b", depends=("a",))), "cycle"),
    ],
    ids=["unknown-node", "duplicate", "unknown-dependency", "cycle"],
)
async def test_reader_plane_refuses_an_unwired_graph(nodes: tuple[NodeUse, ...], problem: str) -> None:
    graphs = {Plane.EVALUATOR: {Target.SKILL: PlaneDecl(summary="s", nodes=nodes)}}
    with pytest.raises(PlaneError, match=problem):
        PlaneReader({"a": CARD, "b": CARD}, graphs).read(Plane.EVALUATOR, Target.SKILL)


async def test_reader_plane_refuses_a_target_without_graph() -> None:
    with pytest.raises(PlaneError, match="no evaluator graph for skill"):
        PlaneReader({}, {Plane.EVALUATOR: {}}).read(Plane.EVALUATOR, Target.SKILL)


async def test_reader_plane_describes_one_target() -> None:
    graphs = {Plane.ENHANCER: {Target.TOOL: PlaneDecl(summary="t", nodes=(NodeUse(use="a", id="x"),))}}
    described = PlaneReader({"a": CARD}, graphs).describe(Plane.ENHANCER, Target.TOOL)
    assert described == "## enhancer/tool — t\n  x                   gate     deterministic  subject  always"
