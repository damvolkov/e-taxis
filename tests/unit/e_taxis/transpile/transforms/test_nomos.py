"""tests/unit/e_taxis/transpile/transforms/nomos: hermes and openhuman tables equal their specs, and each contract holds."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.transpile.engine.context import RowContext
from e_taxis.transpile.transforms import hermes, openhuman
from e_taxis.transpile.transforms.catalog import CATALOG

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree


@pytest.fixture
def nomos(nous_tree: NousTree) -> RowContext:
    return RowContext(
        config=nous_tree.config["nomos"], native=nous_tree.specs["nomos/openhuman"]["native"], bindings={"out": "/o"}
    )


@pytest.fixture
def herm(nous_tree: NousTree) -> RowContext:
    return RowContext(
        config=nous_tree.config["nomos"], native=nous_tree.specs["nomos/hermes"]["native"], bindings={"out": "/o"}
    )


@pytest.mark.parametrize("backend", ["hermes", "openhuman"])
async def test_nomos_table_equals_the_spec(nous_tree: NousTree, backend: str) -> None:
    assert set(CATALOG[backend]) == set(nous_tree.specs[f"nomos/{backend}"]["transforms"])


async def test_nomos_hermes_contracts(herm: RowContext) -> None:
    config = herm.config
    assert (
        hermes.providers_hermes(config["models"]["providers"], herm)["nomos-alibaba"]["api_mode"]
        == "anthropic_messages"
    )
    assert hermes.routes(["alibaba/m"], herm) == [{"provider": "nomos-alibaba", "model": "m"}]
    assert (
        hermes.auxiliary_hermes({"title_generation": "fast"}, herm)["title_generation"]["provider"] == "nomos-alibaba"
    )
    assert hermes.search_backend(config["search"], herm) == "exa"
    assert hermes.approvals({"guard": False, "mode": "full"}, herm) == "off"
    assert hermes.approvals({"guard": True, "mode": "ask"}, herm) == "manual"
    servers = {"s": {"command": ["x", "y"]}, "r": {"url": "http://u", "headers": {"A": "1"}}}
    assert hermes.mcp_hermes(servers, herm) == {
        "s": {"command": "x", "args": ["y"]},
        "r": {"url": "http://u", "headers": {"A": "1"}},
    }


async def test_nomos_openhuman_contracts(nomos: RowContext) -> None:
    config = nomos.config
    assert openhuman.vision_registry("alibaba/q", nomos) == [{"id": "q", "provider": "alibaba", "vision": True}]
    clouds = openhuman.cloud_providers(config["models"]["providers"], nomos)
    assert [cloud["slug"] for cloud in clouds] == ["alibaba", "local", "openhuman", "custom"]
    assert [voice["capability"] for voice in openhuman.voice_providers(config["voice"], nomos)] == ["stt", "tts"]
    sources = openhuman.memory_sources(
        {**config["sources"], "x": {"id": "x", "label": "x", "path": "x", "off": True}}, nomos
    )
    assert [source["target"] for source in sources] == ["/o/memory/inbox/docs", "/o/memory/wiki", "/o/memory/workflow"]
    assert openhuman.search_providers(config["search"]["engines"], nomos)["gemini"] == {
        "enabled": False,
        "route": "managed",
    }
    roots = openhuman.trusted_roots(config["permissions"]["vault"], nomos)
    assert (roots[0], roots[-1]["access"]) == ({"access": "read", "path": "/o/memory/persona"}, "readwrite")
    assert openhuman.jail_ro(config["permissions"], nomos)[-1] == "~/.local/share/uv"
    assert openhuman.jail_rw(["inbox"], nomos) == ["/o/memory/inbox"]
    servers = {"e": {"url": "http://e", "oauth": True, "pinned": True}, "s": {"command": ["c", "a"], "env": {"K": "v"}}}
    assert openhuman.mcp_openhuman(servers, nomos) == [
        {"name": "e", "enabled": False, "endpoint": "http://e"},
        {"name": "s", "enabled": True, "endpoint": "", "command": "c", "args": ["a"], "env": {"K": "v"}},
    ]
    assert openhuman.direct_servers(servers, nomos) == ["e"]
