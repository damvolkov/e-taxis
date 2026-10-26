"""transforms.openhuman: the named transforms of `specs/nomos/openhuman.yaml`, one handler per contract there.

The few constants here (the custom embedder entry, the e-voice provider entries) are OpenHuman's own vocabulary:
what its config schema names, never core content."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "openhuman"
VAULT: str = "memory"
### the memory host finds a custom embedder only by slug among cloud providers (openhuman#6984).
EMBEDDER: Final[Mapping[str, str]] = MappingProxyType(
    {"id": "p_custom_embedder", "slug": "custom", "label": "Embedder (memory host)", "auth_style": "bearer"}
)
AUDIO: str = "openaiaudio"


##### UTILITIES #####
def vault_openhuman(ctx: RowContext, folder: str) -> str:
    return f"{ctx.bindings['out']}/{VAULT}/{folder}"


##### HANDLERS #####
def vision_registry(value: str, _: RowContext) -> list[dict[str, Any]]:
    provider, __, model = value.partition("/")
    return [{"id": model, "provider": provider, "vision": True}]


def cloud_providers(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> list[dict[str, Any]]:
    native = ctx.native
    endpoint = ctx.config["memory"]["embedder"]["endpoint"]
    return [
        *(
            {
                "id": native["ids"][slug],
                "slug": slug,
                "label": data["label"],
                "endpoint": data["endpoint"],
                "auth_style": native["auth"][data["api"]],
            }
            for slug, data in value.items()
        ),
        *(
            {
                "id": data["id"],
                "slug": slug,
                "label": data["label"],
                "endpoint": data["endpoint"],
                "auth_style": data["auth"],
            }
            for slug, data in native["providers"].items()
        ),
        {
            "id": EMBEDDER["id"],
            "slug": EMBEDDER["slug"],
            "label": EMBEDDER["label"],
            "endpoint": endpoint,
            "auth_style": EMBEDDER["auth_style"],
        },
    ]


def voice_providers(value: Mapping[str, Mapping[str, str]], _: RowContext) -> list[dict[str, Any]]:
    stt, tts = value["stt"], value["tts"]
    common = {"auth_style": "bearer", "stt_api_style": AUDIO, "tts_api_style": AUDIO}
    return [
        {
            "id": "vp_evoice_stt",
            "slug": "evoice-stt",
            "label": "e-voice STT",
            "endpoint": stt["endpoint"],
            "auth_style": common["auth_style"],
            "capability": "stt",
            "stt_api_style": AUDIO,
            "tts_api_style": AUDIO,
            "default_stt_model": stt["model"],
        },
        {
            "id": "vp_evoice_tts",
            "slug": "evoice-tts",
            "label": "e-voice TTS",
            "endpoint": tts["endpoint"],
            "auth_style": common["auth_style"],
            "capability": "tts",
            "stt_api_style": AUDIO,
            "tts_api_style": AUDIO,
            "default_tts_voice": tts["voice"],
        },
    ]


def memory_sources(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> list[dict[str, Any]]:
    sync = ctx.config["memory"].get("sync")
    return [
        {
            "id": source["id"],
            "kind": "folder",
            "target": vault_openhuman(ctx, source["path"]),
            "label": source["label"],
            "schedule_mins": sync,
        }
        for source in value.values()
        if not source.get("off", False)
    ]


def search_providers(value: Mapping[str, Mapping[str, Any]], ctx: RowContext) -> dict[str, dict[str, Any]]:
    return {
        name: {"enabled": not engine.get("off", False), "route": ctx.native["routes"][engine["via"]]}
        for name, engine in value.items()
    }


def trusted_roots(value: Mapping[str, list[str]], ctx: RowContext) -> list[dict[str, str]]:
    return [
        *({"access": "read", "path": vault_openhuman(ctx, folder)} for folder in value["read"]),
        *({"access": "readwrite", "path": vault_openhuman(ctx, folder)} for folder in value["write"]),
    ]


def jail_ro(value: Mapping[str, Any], ctx: RowContext) -> list[str]:
    return [*(vault_openhuman(ctx, folder) for folder in value["vault"]["read"]), *value.get("toolchains", [])]


def jail_rw(value: list[str], ctx: RowContext) -> list[str]:
    return [vault_openhuman(ctx, folder) for folder in value]


def mcp_openhuman(value: Mapping[str, Mapping[str, Any]], _: RowContext) -> list[dict[str, Any]]:
    """An oauth server is written disabled — an update, never a removal; it reaches the app through its registry."""
    return [
        {
            "name": name,
            "enabled": not server.get("oauth", False),
            "endpoint": "",
            "command": server["command"][0],
            "args": server["command"][1:],
            "env": dict(server.get("env") or {}),
        }
        if server.get("command")
        else {"name": name, "enabled": not server.get("oauth", False), "endpoint": server["url"]}
        for name, server in value.items()
    ]


def direct_servers(value: Mapping[str, Mapping[str, Any]], _: RowContext) -> list[str]:
    return [name for name, server in value.items() if server.get("pinned")]


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "vision_registry": vision_registry,
        "cloud_providers": cloud_providers,
        "voice_providers": voice_providers,
        "memory_sources": memory_sources,
        "search_providers": search_providers,
        "trusted_roots": trusted_roots,
        "jail_ro": jail_ro,
        "jail_rw": jail_rw,
        "mcp_openhuman": mcp_openhuman,
        "direct_servers": direct_servers,
    }
)
