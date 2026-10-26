"""tests/unit/e_taxis/transpile/engine/combinators: every combinator of the model exists, and each does its one thing."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.engine.combinators import COMBINATORS
from e_taxis.transpile.models.error import RenderError

if TYPE_CHECKING:
    from e_taxis.transpile.engine.context import RowContext
    from e_taxis.transpile.engine.model import SpecModel


async def test_combinators_table_equals_the_model(spec_model: SpecModel) -> None:
    assert set(COMBINATORS) == set(spec_model.combinators)


@pytest.mark.parametrize(
    ("name", "value", "params", "expected"),
    [
        ("tier", "builder", None, "bailian-token-plan-personal/qwen3.8-max"),
        ("names", {"a": 1, "b": 2}, None, ["a", "b"]),
        ("hint", {"a": 1, "b": 2}, None, "[a] [b]"),
        (
            "denied",
            {"read": "allow", "task": "deny", "skill": {"*": "deny"}, "bash": {"*": "allow", "x": "deny"}},
            {"tools": {"read": ["Read"], "task": ["Agent"], "skill": ["Skill"], "bash": ["Bash"]}},
            ["Agent", "Skill"],
        ),
        ("template", "parakeet", "evoice-stt:{value}@{out}", "evoice-stt:parakeet@/out"),
        ("table", "alibaba", "names", "nomos-alibaba"),
        ("replace", "a/b/c", {"old": "/", "new": ":", "count": 1}, "a:b/c"),
        ("split", "a/b/c", {"on": "/", "take": "head"}, "a"),
        ("split", "a/b/c", {"on": "/", "take": "tail"}, "b/c"),
        ("pluck", {"x": {"id": 1}, "y": {"id": 2}}, "id", [1, 2]),
        ("pick", {"a": 1, "b": 2, "c": 3}, ["a", "c", "z"], {"a": 1, "c": 3}),
        ("join", [1, 2], ",", "1,2"),
        ("falsy", 0, None, None),
        ("falsy", 5, "", 5),
        ("falsy", 0, "native.names.alibaba", "nomos-alibaba"),
        ("equals", "workspace", "workspace", True),
        ("wrap", ["exa"], "search", {"search": ["exa"]}),
        ("prefix_each", ["1"], "discord:", ["discord:1"]),
        ("bind", "{out}/a", None, "/out/a"),
        ("bind", ["{out}/a", "b"], None, ["/out/a", "b"]),
    ],
    ids=[
        "tier",
        "names",
        "hint",
        "denied",
        "template",
        "table",
        "replace",
        "head",
        "tail",
        "pluck",
        "pick",
        "join",
        "falsy-null",
        "falsy-kept",
        "falsy-native",
        "equals",
        "wrap",
        "prefix",
        "bind",
        "bind-list",
    ],
)
async def test_combinators_apply(ctx: RowContext, name: str, value: Any, params: Any, expected: Any) -> None:
    assert COMBINATORS[name](value, params, ctx) == expected


@pytest.mark.parametrize(
    ("name", "value", "params"), [("tier", "ghost", None), ("table", "ghost", "names")], ids=["tier", "table"]
)
async def test_combinators_lookup_without_entry_refuses(ctx: RowContext, name: str, value: Any, params: Any) -> None:
    with pytest.raises(RenderError):
        COMBINATORS[name](value, params, ctx)


@pytest.mark.parametrize(
    ("placeholder", "expected"),
    [("${n}", "go $2 then $1 and ${other}"), ("${name}", "go $b then $a and ${other}")],
    ids=["position", "name"],
)
async def test_combinators_positional(ctx: RowContext, placeholder: str, expected: str) -> None:
    instance = ctx.per({"inputs": {"a": "x", "b": "y"}}, "cmd")
    assert (
        COMBINATORS["positional"](
            "go ${b} then $a and ${other}", {"slot": "inputs", "placeholder": placeholder}, instance
        )
        == expected
    )


async def test_combinators_graph_renders_steps_loop_and_output(ctx: RowContext) -> None:
    nodes = [
        {"id": "a", "run": "make", "instruction": "build it"},
        {"id": "b", "depends": ["a"], "actor": "scout", "instruction": "look", "when": {"op": ["x", "y"], "mode": "z"}},
    ]
    instance = ctx.per({"loop": {"nodes": ["a", "b"], "max": 2, "until": "b"}, "output": {"type": "report"}}, "w")
    text = COMBINATORS["graph"](nodes, {"output": "output", "loop": "loop", "start": "start", "done": "done"}, instance)
    assert "    start --> a\n    a --> b\n    b --> done" in text
    assert "run: `make`\n\nbuild it" in text
    assert "*only when `op` is `x` or `y`*" in text
    assert "*only when `mode` is `z`*" in text
    assert "@scout look" in text
    assert "## loop" in text
    assert "## output\n\ntype: report" in text


@pytest.mark.parametrize(
    "nodes",
    [[], [{"id": "start", "run": "x"}], [{"id": "a", "depends": ["ghost"], "run": "x"}], [{"id": "a"}]],
    ids=["empty", "terminal", "edge", "no-body"],
)
async def test_combinators_graph_refuses(ctx: RowContext, nodes: list[dict[str, Any]]) -> None:
    with pytest.raises(RenderError):
        COMBINATORS["graph"](nodes, {"output": "o", "loop": "l", "start": "start", "done": "done"}, ctx.per({}, "w"))


async def test_combinators_graph_refuses_a_loop_over_undeclared_nodes(ctx: RowContext) -> None:
    instance = ctx.per({"loop": {"nodes": ["ghost"], "max": 1, "until": "ghost"}}, "w")
    with pytest.raises(RenderError, match="loop"):
        COMBINATORS["graph"](
            [{"id": "a", "run": "x"}], {"output": "o", "loop": "loop", "start": "s", "done": "d"}, instance
        )
