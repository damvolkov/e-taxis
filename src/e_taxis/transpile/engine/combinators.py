"""engine.combinators: the closed vocabulary of `specs/base.yaml · combinators` — trivial pure functions.

Each handler takes the row's value, the combinator's params and the read-only context, and returns the next value.
`COMBINATORS` is the whole table; a test holds it equal to the model's list, so a combinator the spec names and
this table lacks fails the gate, never a render. Whatever these cannot express is a named transform of the
backend (`transpile/transforms/<backend>.py`)."""

import re
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, Final

from e_taxis.transpile.engine.context import MISSING, RowContext
from e_taxis.transpile.models.error import RenderError

##### DEFAULTS #####
### `${name}` or `$name` in a template: the named input it refers to.
NAME: Final = re.compile(r"\$\{?([a-z_][a-z0-9_-]*)\}?(?!\w)")
SPLIT: str = "/"
NATIVE: str = "native."


##### UTILITIES #####
def resolve_param(param: Any, ctx: RowContext) -> Any:
    """A literal, or `native.<path>` read from the spec's native tables."""
    match param:
        case str() if param.startswith(NATIVE):
            return ctx.path(param)
        case _:
            return param


##### HANDLERS #####
def tier(value: str, _: Any, ctx: RowContext) -> str:
    """A house tier → `<provider id>/<model>`: the provider alias of `models.tiers.<tier>.model`, by its `id`."""
    match ctx.path(f"models.tiers.{value}.model"):
        case str() as route:
            alias, _, model = route.partition(SPLIT)
            return f"{ctx.path(f'models.providers.{alias}.id')}/{model}"
        case _:
            msg = f"tier `{value}` is declared nowhere in models.tiers"
            raise RenderError(msg)


def names(value: Mapping[str, Any], _: Any, __: RowContext) -> list[str]:
    return list(value)


def hint(value: Mapping[str, Any], _: Any, __: RowContext) -> str:
    return " ".join(f"[{name}]" for name in value)


def denied(value: Mapping[str, Any], params: Mapping[str, Any], ctx: RowContext) -> list[str]:
    """The backend tools a house permission vetoes outright: a flat `deny`, or patterns that only deny."""
    return [
        tool
        for key, tools in resolve_param(params["tools"], ctx).items()
        if (rule := value.get(key)) == "deny" or (isinstance(rule, Mapping) and set(rule.values()) == {"deny"})
        for tool in tools
    ]


def template(value: Any, params: str, ctx: RowContext) -> str:
    return ctx.bind(params.replace("{value}", str(value)))


def table(value: Any, params: str, ctx: RowContext) -> Any:
    match ctx.path(f"native.{params}.{value}"):
        case found if found is MISSING:
            msg = f"native table `{params}` has no entry `{value}`"
            raise RenderError(msg)
        case found:
            return found


def replace(value: str, params: Mapping[str, Any], _: RowContext) -> str:
    return value.replace(params["old"], params["new"], params["count"])


def split(value: str, params: Mapping[str, str], _: RowContext) -> str:
    head, __, tail = value.partition(params["on"])
    return head if params["take"] == "head" else tail


def pluck(value: Mapping[str, Mapping[str, Any]], params: str, _: RowContext) -> list[Any]:
    return [item[params] for item in value.values()]


def pick(value: Mapping[str, Any], params: list[str], _: RowContext) -> dict[str, Any]:
    return {key: value[key] for key in params if key in value}


def join(value: list[Any], params: str, _: RowContext) -> str:
    return params.join(str(item) for item in value)


def falsy(value: Any, params: Any, ctx: RowContext) -> Any:
    return value or resolve_param(params, ctx)


def equals(value: Any, params: Any, _: RowContext) -> bool:
    return value == params


def wrap(value: Any, params: str, _: RowContext) -> dict[str, Any]:
    return {params: value}


def prefix_each(value: list[Any], params: str, _: RowContext) -> list[str]:
    return [f"{params}{item}" for item in value]


def bind(value: str | list[str], _: Any, ctx: RowContext) -> str | list[str]:
    return ctx.bind(value) if isinstance(value, str) else [ctx.bind(item) for item in value]


def positional(value: str, params: Mapping[str, str], ctx: RowContext) -> str:
    """`${name}` of a declared input → the backend's placeholder: `${n}` (1-based position) or `${name}`."""
    declared = list((ctx.instance or {}).get(params["slot"]) or {})
    return NAME.sub(
        lambda found: (
            params["placeholder"]
            .replace("{n}", str(declared.index(found.group(1)) + 1))
            .replace("{name}", found.group(1))
            if found.group(1) in declared
            else found.group(0)
        ),
        value,
    )


def graph(value: list[Mapping[str, Any]], params: Mapping[str, str], ctx: RowContext) -> str:
    """A workflow's nodes rendered as the lead reads them: mermaid, steps in order, loop and output blocks."""
    instance = ctx.instance or {}
    start, done = params["start"], params["done"]
    ids = [node["id"] for node in value]
    parents = {node["id"]: list(node.get("depends") or []) or [start] for node in value}
    loop = instance.get(params["loop"])
    output = instance.get(params["output"])
    problems = [
        *(["an empty graph is not a workflow"] if not value else []),
        *([f"node ids collide with the terminals: {sorted(clash)}"] if (clash := set(ids) & {start, done}) else []),
        *(
            [f"edges to undeclared or terminal nodes: {sorted(bad)}"]
            if (bad := {p for ps in parents.values() for p in ps if p != start and p not in ids})
            else []
        ),
        *(
            [f"loop names undeclared nodes: {sorted(set(loop['nodes']) - set(ids))}"]
            if loop and not set(loop["nodes"]) <= set(ids)
            else []
        ),
    ]
    match problems:
        case []:
            pass
        case _:
            raise RenderError("; ".join(problems))
    depended = {p for ps in parents.values() for p in ps}
    edges = [
        *(f"    {parent} --> {node_id}" for node_id in ids for parent in parents[node_id]),
        *(f"    {node_id} --> {done}" for node_id in ids if node_id not in depended),
        *(
            [f'    {loop["nodes"][-1]} -.->|"until {loop["until"]} · max {loop["max"]}"| {loop["nodes"][0]}']
            if loop
            else []
        ),
    ]
    steps = "\n\n".join(
        f"### {node['id']} (depends: {', '.join(parents[node['id']])})\n\n{graph_step(node)}" for node in value
    )
    blocks = [
        "```mermaid\nflowchart TD\n" + "\n".join(edges) + "\n```",
        f"## steps\n\n{steps}",
        *([graph_loop(loop)] if loop else []),
        *(["## output\n\n" + "\n".join(f"{key}: {item}" for key, item in output.items())] if output else []),
    ]
    return "\n\n".join(blocks)


def graph_step(node: Mapping[str, Any]) -> str:
    """One step's body: its conditions, then the command to run or the instruction for its actor."""
    when = "".join(
        f"*only when `{key}` is {' or '.join(f'`{v}`' for v in ([values] if isinstance(values, str) else values))}*\n\n"
        for key, values in (node.get("when") or {}).items()
    )
    match node:
        case {"run": str() as command}:
            note = f"\n\n{node['instruction']}" if node.get("instruction") else ""
            return f"{when}run: `{command}`{note}"
        case {"instruction": str() as text}:
            return when + (f"@{node['actor']} " if node.get("actor") else "") + text
        case _:
            msg = f"step `{node.get('id')}`: needs `run` or `instruction`"
            raise RenderError(msg)


def graph_loop(loop: Mapping[str, Any]) -> str:
    """The loop as the lead reads it: which steps repeat, how many times at most, and what ends it."""
    return (
        f"## loop\n\nRepeat {' → '.join(f'`{node}`' for node in loop['nodes'])} at most {loop['max']} times. "
        f"`{loop['until']}` ends it: its command exits 0 (closed), or prints the same open set as the "
        "previous iteration (stalled). After an ending check every remaining step of the loop is skipped "
        "and the run continues past it. `{{iteration}}` is the current pass, from 1."
    )


##### TABLE #####
COMBINATORS: Final[Mapping[str, Callable[[Any, Any, RowContext], Any]]] = MappingProxyType(
    {
        "tier": tier,
        "names": names,
        "hint": hint,
        "denied": denied,
        "template": template,
        "table": table,
        "replace": replace,
        "split": split,
        "pluck": pluck,
        "pick": pick,
        "join": join,
        "falsy": falsy,
        "equals": equals,
        "wrap": wrap,
        "prefix_each": prefix_each,
        "bind": bind,
        "positional": positional,
        "graph": graph,
    }
)
