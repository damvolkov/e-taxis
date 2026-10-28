"""transforms.claudecode: the named transforms of `specs/tekton/claudecode.yaml`, one handler per contract there.

`TRANSFORMS` is the table the renderer reads; a test holds it equal to the spec's `transforms:` block."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.transforms.backends import reaches
from e_taxis.transpile.transforms.hooks import command_hook, matchers_hook, native_hook, reaching_hooks

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "claudecode"
SIGNALS: Final[tuple[str, ...]] = ("metrics", "logs", "traces")


##### HANDLERS #####
def claude_telemetry(value: Mapping[str, Any], _: RowContext) -> dict[str, str]:
    signals = value["signals"]
    return {
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        **{f"OTEL_{signal.upper()}_EXPORTER": "otlp" for signal in SIGNALS if signal in signals},
        "OTEL_EXPORTER_OTLP_PROTOCOL": value["protocol"],
        "OTEL_EXPORTER_OTLP_ENDPOINT": value["endpoint"],
    }


def claude_hooks(value: Mapping[str, Sequence[Mapping[str, Any]]], ctx: RowContext) -> dict[str, list[dict[str, Any]]]:
    """Each house event under its Claude Code name: one entry per hook that reaches Claude, matchers joined by `|`."""
    return {
        native["event"]: [
            ({"matcher": "|".join(matchers)} if (matchers := matchers_hook(event, hook, native, ctx)) else {})
            | {"hooks": [{"type": "command", "command": command_hook(hook, ctx)}]}
            for hook in hooks
        ]
        for event, hooks in reaching_hooks(value, BACKEND)
        for native in (native_hook(event, ctx),)
    }


def claude_plugins(value: list[str], _: RowContext) -> dict[str, bool]:
    return dict.fromkeys(value, True)


def at_imports(value: list[Any], ctx: RowContext) -> str:
    return "".join(
        f"@{ctx.bind(entry if isinstance(entry, str) else entry['path'])}\n"
        for entry in value
        if reaches(entry, BACKEND)
    )


def mcp_claudecode(value: Mapping[str, Any], ctx: RowContext) -> dict[str, Any] | None:
    """One registry entry in the shape Claude stores it, or None when the server does not reach Claude."""
    match (reaches(value, BACKEND), value.get("command")):
        case (False, _):
            return None
        case (_, [head, *args]):
            shape = {
                "type": "stdio",
                "command": ctx.bind(head),
                "args": [ctx.bind(arg) for arg in args],
                "env": {key: ctx.bind(item) for key, item in (value.get("env") or {}).items()},
            }
        case _:
            shape = {"type": "http", "url": ctx.bind(value["url"]), "headers": dict(value.get("headers") or {})}
    return {key: item for key, item in shape.items() if item or key == "args"}


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "claude_telemetry": claude_telemetry,
        "claude_hooks": claude_hooks,
        "claude_plugins": claude_plugins,
        "at_imports": at_imports,
        "mcp_claudecode": mcp_claudecode,
    }
)
