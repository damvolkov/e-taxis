"""transforms.hooks: the house hook vocabulary read against a spec's `native.hooks` and `native.tools` — shared by
every backend that realizes hooks.

A realization (`native.hooks.<event>`) says how its harness meets the moment. Its matcher rule is one of three:
`tools: true` — the matchers are house tools, translated through `native.tools`; `matchers: [...]` — the values
the realization satisfies whole, so a hook's matchers must lie within them and are dropped; neither — the harness
filters on the house values itself. What a backend cannot realize refuses the render, never a silent hook."""

import shlex
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.engine.context import MISSING
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.transforms.backends import reaches

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from e_taxis.transpile.engine.context import RowContext


##### UTILITIES #####
def reaching_hooks(
    value: Mapping[str, Sequence[Mapping[str, Any]]], backend: str
) -> Iterator[tuple[str, list[Mapping[str, Any]]]]:
    """Each event in core order with the hooks that reach `backend`; an event none reaches is skipped."""
    yield from (
        (event, found)
        for event, hooks in value.items()
        if (found := [hook for hook in hooks if reaches(hook, backend)])
    )


def native_hook(event: str, ctx: RowContext) -> Mapping[str, Any]:
    """The backend's realization of a house event."""
    match ctx.path(f"native.hooks.{event}"):
        case found if found is MISSING:
            msg = f"hook event `{event}` has no realization in native.hooks"
            raise RenderError(msg)
        case found:
            return found


def tool_hook(tool: str, ctx: RowContext) -> list[str]:
    """A house tool as the backend names it."""
    match ctx.path(f"native.tools.{tool}"):
        case found if found is MISSING:
            msg = f"hook matcher `{tool}` is a house tool native.tools does not name"
            raise RenderError(msg)
        case found:
            return list(found)


def matchers_hook(event: str, hook: Mapping[str, Any], native: Mapping[str, Any], ctx: RowContext) -> list[str]:
    """The matchers a realization receives: tools translated, a whole set dropped, anything else as it is."""
    matchers = list(hook.get("matchers") or [])
    match (native.get("tools", False), native.get("matchers")):
        case (True, _):
            return list(dict.fromkeys(name for tool in matchers for name in tool_hook(tool, ctx)))
        case (_, list() as honoured) if set(matchers) <= set(honoured):
            return []
        case (_, list() as honoured):
            msg = f"hook event `{event}` honours only {sorted(honoured)}, not {sorted(set(matchers) - set(honoured))}"
            raise RenderError(msg)
        case _:
            return matchers


def command_hook(hook: Mapping[str, Any], ctx: RowContext) -> str:
    """The hook's argv as one shell command, every binding formatted."""
    return shlex.join(ctx.bind(arg) for arg in hook["run"])
