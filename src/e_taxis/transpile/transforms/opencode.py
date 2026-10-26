"""transforms.opencode: the named transforms of `specs/tekton/opencode.yaml`, one handler per contract there."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.engine.combinators import tier
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.transforms.claudecode import reaches

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "opencode"
SPLIT: str = "/"


##### HANDLERS #####
def instructions_opencode(value: list[Any], ctx: RowContext) -> list[str]:
    return [ctx.bind(entry if isinstance(entry, str) else entry["path"]) for entry in value if reaches(entry, BACKEND)]


def agents_registry(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> dict[str, dict[str, Any]]:
    """Overrides then system agents, each house tier resolved; a name in both has no single meaning."""
    overrides, system = value.get("overrides") or {}, value.get("system") or {}
    match sorted(set(overrides) & set(system)):
        case []:
            return {
                name: {**config, **({"model": tier(config["model"], None, ctx)} if "model" in config else {})}
                for name, config in {**overrides, **system}.items()
            }
        case twice:
            msg = f"agents named both an override and a system agent: {', '.join(twice)}"
            raise RenderError(msg)


def providers_tree(value: Mapping[str, Any], _: RowContext) -> dict[str, dict[str, Any]]:
    """One entry per provider id, carrying the tiers whose alias names it, in tier order; empty keys omitted."""
    providers, tiers = value["providers"], value["tiers"]
    return {
        data["id"]: {
            "npm": data["sdk"],
            "name": data["display"],
            "options": {
                key: item
                for key, item in {"baseURL": data.get("base_url"), "apiKey": data.get("api_key")}.items()
                if item
            },
            "models": {
                spec["model"].partition(SPLIT)[2]: {
                    key: item
                    for key, item in {
                        "name": name,
                        "reasoning": spec.get("reasoning"),
                        "limit": spec.get("limits"),
                        "modalities": spec.get("modalities"),
                        "options": spec.get("options"),
                    }.items()
                    if item
                }
                for name, spec in tiers.items()
                if spec["model"].partition(SPLIT)[0] == alias
            },
        }
        for alias, data in providers.items()
    }


def npm_dependency(value: str, _: RowContext) -> dict[str, str]:
    package, __, version = value.rpartition("@")
    return {package: version}


def mcp_opencode(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> dict[str, dict[str, Any]]:
    return {
        name: {
            key: item
            for key, item in (
                {
                    "type": "local",
                    "command": [ctx.bind(arg) for arg in server["command"]],
                    "environment": {k: ctx.bind(v) for k, v in (server.get("env") or {}).items()},
                }
                if server.get("command")
                else {"type": "remote", "url": ctx.bind(server["url"]), "headers": dict(server.get("headers") or {})}
            ).items()
            if item
        }
        | {"enabled": True}
        for name, server in value.items()
        if reaches(server, BACKEND)
    }


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "instructions_opencode": instructions_opencode,
        "agents_registry": agents_registry,
        "providers_tree": providers_tree,
        "npm_dependency": npm_dependency,
        "mcp_opencode": mcp_opencode,
    }
)
