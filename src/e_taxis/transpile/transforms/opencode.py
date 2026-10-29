"""transforms.opencode: the named transforms of `specs/tekton/opencode.yaml`, one handler per contract there."""

import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.engine.combinators import tier
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.transforms.backends import reaches
from e_taxis.transpile.transforms.hooks import command_hook, matchers_hook, native_hook, reaching_hooks

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "opencode"
SPLIT: str = "/"
### the core writes an env reference as Claude reads it, `${NAME}`; OpenCode reads `{env:NAME}`.
ENV_REF: Final[re.Pattern[str]] = re.compile(r"\$\{(\w+)\}")


##### UTILITIES #####
def env_opencode(text: str) -> str:
    """`${NAME}` written the way OpenCode expands it: `{env:NAME}`."""
    return ENV_REF.sub(r"{env:\1}", text)


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


def model_entry(tiers: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """One model entry for every tier routed to it, named by them all; they must agree on the rest."""
    shapes = [
        {
            key: item
            for key, item in {
                "reasoning": spec.get("reasoning"),
                "limit": spec.get("limits"),
                "modalities": spec.get("modalities"),
                "options": spec.get("options"),
            }.items()
            if item
        }
        for spec in tiers.values()
    ]
    match [shape for shape in shapes if shape != shapes[0]]:
        case []:
            return {"name": SPLIT.join(tiers)} | shapes[0]
        case _:
            msg = f"tiers routed to one model with different settings: {', '.join(tiers)}"
            raise RenderError(msg)


def providers_tree(value: Mapping[str, Any], _: RowContext) -> dict[str, dict[str, Any]]:
    """One entry per provider id, each model once in tier order, named by the tiers routed to it; empty keys omitted."""
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
                model: model_entry({name: spec for name, spec in tiers.items() if spec["model"] == route})
                for route in dict.fromkeys(spec["model"] for spec in tiers.values())
                if (parts := route.partition(SPLIT))[0] == alias and (model := parts[2])
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
                    "environment": {k: env_opencode(ctx.bind(v)) for k, v in (server.get("env") or {}).items()},
                }
                if server.get("command")
                else {
                    "type": "remote",
                    "url": ctx.bind(server["url"]),
                    "headers": {k: env_opencode(v) for k, v in (server.get("headers") or {}).items()},
                }
            ).items()
            if item
        }
        | {"enabled": True}
        for name, server in value.items()
        if reaches(server, BACKEND)
    }


def opencode_hooks(value: Mapping[str, Sequence[Mapping[str, Any]]], ctx: RowContext) -> list[dict[str, Any]]:
    """One binding per hook that reaches OpenCode: where plugins/hooks.js registers it, and the command it runs."""
    return [
        {
            "event": event,
            "domain": native["domain"],
            "name": native["name"],
            "when": dict(native.get("when") or {}),
            "effect": native["effect"],
            "matchers": matchers_hook(event, hook, native, ctx),
            "command": command_hook(hook, ctx),
        }
        for event, hooks in reaching_hooks(value, BACKEND)
        for native in (native_hook(event, ctx),)
        for hook in hooks
    ]


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "instructions_opencode": instructions_opencode,
        "agents_registry": agents_registry,
        "providers_tree": providers_tree,
        "npm_dependency": npm_dependency,
        "opencode_hooks": opencode_hooks,
        "mcp_opencode": mcp_opencode,
    }
)
