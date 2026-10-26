"""tests/unit/e_taxis/workflow/models/workflow: the typed workflow — its static check, its kinds, its writers."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.workflow import Node, Param, ParamType, StepKind, Workflow

if TYPE_CHECKING:
    from collections.abc import Callable

AGENTS = frozenset({"scout", "auditor"})
HOOKS = frozenset({"autolearn.mjs"})


async def test_workflow_kind_follows_what_a_node_declares() -> None:
    kinds = [
        Node(id="a", run="x").kind,
        Node(id="b", actor="scout", instruction="i").kind,
        Node(id="c", instruction="i").kind,
    ]
    assert kinds == [StepKind.RUN, StepKind.AGENT, StepKind.LEAD]


async def test_workflow_bare_parameter_is_its_doc(flow: Callable[..., Workflow]) -> None:
    w = flow({"id": "a", "run": "x"}, parameters={"entity": "the kind", "apply": {"type": "bool", "default": "false"}})
    assert w.params == {"entity": Param(doc="the kind"), "apply": Param(type=ParamType.BOOL, default="false")}


async def test_workflow_conditions_are_tuples() -> None:
    node = Node(id="a", run="x", when={"op": "update", "p": ("a", "b")})
    assert node.conditions == {"op": ("update",), "p": ("a", "b")}


async def test_workflow_clean_graph_has_no_problems(flow: Callable[..., Workflow]) -> None:
    w = flow(
        {"id": "scan", "run": "x", "outputs": [{"name": "deltas", "model": "Deltas"}]},
        {
            "id": "mine",
            "depends": ["scan"],
            "actor": "scout",
            "instruction": "i",
            "hooks": ["autolearn.mjs"],
            "inputs": [{"name": "deltas", "model": "Deltas", "from": "scan.deltas"}],
        },
        parameters={"op": "x"},
    )
    assert w.problems(AGENTS, HOOKS, {"Deltas"}) == ()


@pytest.mark.parametrize(
    ("nodes", "problem"),
    [
        (({"id": "a", "run": "x"}, {"id": "a", "run": "y"}), "duplicate step a"),
        (({"id": "a", "depends": ["ghost"], "run": "x"},), "depends on unknown step ghost"),
        (({"id": "a", "actor": "nobody", "instruction": "i"},), "unknown agent nobody"),
        (({"id": "a", "run": "x", "hooks": ["nope.sh"]},), "unknown hook nope.sh"),
        (({"id": "a", "run": "x", "actor": "scout"},), "`run` and `actor` both set"),
        (({"id": "a"},), "needs `run`, `actor` or `instruction`"),
        (({"id": "a", "run": "x", "when": {"ghost": "1"}},), "undeclared parameter ghost"),
        (({"id": "a", "depends": ["b"], "run": "x"}, {"id": "b", "depends": ["a"], "run": "y"}), "cycle"),
        (
            (
                {"id": "a", "run": "x", "inputs": [{"name": "i", "model": "M", "from": "b.o"}]},
                {"id": "b", "run": "y", "outputs": [{"name": "o", "model": "M"}]},
            ),
            "which no ancestor writes",
        ),
        (
            (
                {"id": "b", "run": "y", "outputs": [{"name": "o", "model": "M"}]},
                {"id": "a", "depends": ["b"], "run": "x", "inputs": [{"name": "i", "model": "N", "from": "b.o"}]},
            ),
            "expects N, b.o writes M",
        ),
    ],
    ids=["dup", "depends", "agent", "hook", "run-and-actor", "empty", "when", "cycle", "port-orphan", "port-model"],
)
async def test_workflow_problems(
    flow: Callable[..., Workflow], nodes: tuple[dict[str, Any], ...], problem: str
) -> None:
    assert any(problem in found for found in flow(*nodes).problems(AGENTS, HOOKS))


async def test_workflow_unknown_field_is_refused(flow: Callable[..., Workflow]) -> None:
    with pytest.raises(msgspec.ValidationError, match="unknown field"):
        flow({"id": "a", "run": "x", "tools": ["grep"]})


async def test_workflow_bad_loop_is_a_problem(flow: Callable[..., Workflow]) -> None:
    w = flow({"id": "a", "run": "x"}, loop={"nodes": ["a", "ghost"], "max": 0, "until": "zed"})
    found = w.problems(AGENTS, HOOKS)
    assert {
        "loop: unknown step ghost",
        "loop: until zed is not one of its steps",
        "loop: max must be at least 1",
    } <= set(found)


async def test_workflow_port_model_needs_a_schema(flow: Callable[..., Workflow]) -> None:
    w = flow({"id": "a", "run": "x", "outputs": [{"name": "o", "model": "Ghost"}]})
    assert any("has no schema" in found for found in w.problems(AGENTS, HOOKS, {"Real"}))
    assert w.problems(AGENTS, HOOKS) == ()


async def test_workflow_writers_are_the_steps_writing_a_model(flow: Callable[..., Workflow]) -> None:
    w = flow(
        {"id": "a", "actor": "scout", "instruction": "i", "outputs": [{"name": "m", "model": "Mining"}]},
        {"id": "b", "actor": "scout", "instruction": "i", "outputs": [{"name": "m", "model": "Mining"}]},
        {"id": "c", "run": "x", "outputs": [{"name": "g", "model": "Grades"}]},
    )
    assert (w.writers("Mining"), w.writers("Grades"), w.writers("Ghost")) == (("a", "b"), ("c",), ())
