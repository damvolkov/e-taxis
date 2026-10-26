"""transforms.hermes: the named transforms of `specs/nomos/hermes.yaml`, one handler per contract there."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "hermes"
SPLIT: str = "/"
OFF: str = "off"


##### UTILITIES #####
def route_hermes(value: str, ctx: RowContext) -> dict[str, str]:
    """`alias/model` of the core as Hermes's `{provider, model}`, the alias under its Hermes name."""
    alias, __, model = value.partition(SPLIT)
    return {"provider": ctx.native["names"][alias], "model": model}


##### HANDLERS #####
def providers_hermes(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> dict[str, dict[str, str]]:
    return {
        ctx.native["names"][alias]: {
            "base_url": data["endpoint"],
            "api_mode": ctx.native["api"][data["api"]],
            "key_env": data["key"],
        }
        for alias, data in value.items()
    }


def routes(value: list[str], ctx: RowContext) -> list[dict[str, str]]:
    return [route_hermes(entry, ctx) for entry in value]


def auxiliary_hermes(value: Mapping[str, str], ctx: RowContext) -> dict[str, dict[str, str]]:
    roles = ctx.config["models"]["roles"]
    return {task: route_hermes(roles[role], ctx) for task, role in value.items()}


def search_backend(value: Mapping[str, Any], ctx: RowContext) -> str:
    engines = value["engines"]
    first = next(name for name in value["order"] if not engines[name].get("off", False))
    return ctx.native["search"][first]


def approvals(value: Mapping[str, Any], ctx: RowContext) -> str:
    return ctx.native["levels"][value["mode"]] if value["guard"] else OFF


def mcp_hermes(value: Mapping[str, Mapping[str, Any]], _: RowContext) -> dict[str, dict[str, Any]]:
    return {
        name: {
            key: item
            for key, item in (
                {"command": server["command"][0], "args": server["command"][1:], "env": dict(server.get("env") or {})}
                if server.get("command")
                else {"url": server["url"], "headers": dict(server.get("headers") or {})}
            ).items()
            if item or key == "args"
        }
        for name, server in value.items()
    }


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "providers_hermes": providers_hermes,
        "routes": routes,
        "auxiliary_hermes": auxiliary_hermes,
        "search_backend": search_backend,
        "approvals": approvals,
        "mcp_hermes": mcp_hermes,
    }
)
