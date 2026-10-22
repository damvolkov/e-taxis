"""The openhuman config: core/nomos/config rendered to config.toml by dotted path — the app's own leaves untouched."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.transpiler.render import Transpiler


async def test_render_toml_core_names_no_harness() -> None:
    harness = re.compile(r"openhuman|hermes|tinyhumans|managed|\bdirect\b|\bp_[a-z]|jwt", re.IGNORECASE)
    leaks = {
        path.name: found
        for path in sorted((settings.ROOT / "core/nomos/config").glob("*.yaml"))
        if (found := harness.findall(path.read_text()))
    }
    assert not leaks


async def test_render_toml_writes_only_owned_paths(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    data = tomllib.loads(render.files[path])
    assert data["primary_cloud"] == "p_alibaba_tp01k" and data["stt_provider"].startswith("evoice-stt:")
    assert data["memory"]["embedding_dimensions"] == 1024 and "gemini" not in data["search"]
    assert [(s["id"], s["target"]) for s in data["memory"]["sources"]][:2] == [
        ("src_vault_notes", str(tmp_path / "memory/inbox/docs")),
        ("kb_wiki", str(tmp_path / "memory/wiki")),
    ]


async def test_render_toml_custom_embedder_reachable_by_slug(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    custom = [p for p in data["cloud_providers"] if p["slug"] == "custom"]
    assert data["memory"]["embedding_provider"] == f"custom:{data['custom_embeddings']['endpoint']}"
    assert [p["endpoint"] for p in custom] == [data["custom_embeddings"]["endpoint"]]


async def test_render_toml_tools_at_full_performance(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    agent, context, http = data["agent"], data["context"], data["http_request"]
    assert agent["max_tool_iterations"] >= 100 and agent["parallel_tools"] and agent["agent_timeout_secs"] >= 600
    assert context["tool_result_budget_bytes"] >= 100_000 and http["max_response_size"] >= 10_000_000
    assert data["multimodal"]["allow_remote_fetch"] and data["multimodal_files"]["allow_remote_fetch"]
    assert data["search"]["providers"]["gemini"]["enabled"] is False and data["search"]["providers"]["exa"]["enabled"]


async def test_render_toml_channel_waits_longer_than_the_agent_runs(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    assert data["channels_config"]["message_timeout_secs"] > data["agent"]["agent_timeout_secs"]


async def test_render_toml_discord_open_to_direct_messages(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    discord = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["channels_config"][
        "discord"
    ]
    assert discord["allowed_users"] and "channel_id" not in discord


async def test_render_toml_discord_files_trust_only_the_owner(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    trusted = data["multimodal_files"]["trusted_channel_senders"]
    assert trusted == [f"discord:{u}" for u in data["channels_config"]["discord"]["allowed_users"]]


async def test_render_toml_vision_role_is_routed_and_flagged(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    provider, model = data["vision_provider"].split(":", 1)
    assert {"id": model, "provider": provider, "vision": True} in data["model_registry"]


async def test_render_toml_export_keeps_the_apps_model_registry(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[[model_registry]]\nid = "qwen3-max"\nprovider = "qwen"\nvision = false\n')
    render.export()
    registry = tomllib.loads(path.read_text())["model_registry"]
    assert {"id": "qwen3-max", "provider": "qwen", "vision": False} in registry
    assert any(entry["vision"] for entry in registry if entry["id"] != "qwen3-max")


async def test_render_toml_export_drops_owned_keys_the_render_omits(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[channels_config.discord]\nbot_token = "t"\nguild_id = "g"\nchannel_id = "c"\nmention_only = false\n'
    )
    render.export()
    discord = tomllib.loads(path.read_text())["channels_config"]["discord"]
    assert "channel_id" not in discord and discord["guild_id"] == "g" and discord["mention_only"] is False
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_export_keeps_the_apps_own_list_items(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[[memory.sources]]\nid = "stale"\nkind = "folder"\ntarget = "/old"\n'
        '[[memory.sources]]\nid = "gh"\nkind = "github"\ntarget = "owner/repo"\n'
    )
    render.export()
    sources = tomllib.loads(path.read_text())["memory"]["sources"]
    ids = [s["id"] for s in sources]
    assert "gh" in ids and "stale" in ids and "src_vault_notes" in ids
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_export_updates_a_folder_in_place_and_never_drops_one(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[[memory.sources]]\nid = "src_vault_notes"\nkind = "folder"\nlabel = "old"\ntarget = "/old"\n'
        '[[memory.sources]]\nid = "kb_native"\nkind = "folder"\nlabel = "app"\ntarget = "/app"\n'
    )
    render.export()
    sources = {s["id"]: s for s in tomllib.loads(path.read_text())["memory"]["sources"]}
    assert (
        sources["src_vault_notes"]["target"] == str(tmp_path / "memory/inbox/docs")
        and sources["kb_native"]["target"] == "/app"
    )
    assert list(sources).count("src_vault_notes") == 1


async def test_render_toml_export_never_creates_a_harness_table(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text("schema_version = 13\n")
    render.export()
    assert "channels_config" not in tomllib.loads(path.read_text())
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_export_keeps_the_apps_leaves_and_judges_owned_drift(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('schema_version = 13\n[search.gemini]\napi_key = "app-secret"\n[memory]\nauto_save = true\n')
    render.export()
    data = tomllib.loads(path.read_text())
    assert (
        data["schema_version"] == 13
        and data["search"]["gemini"]["api_key"] == "app-secret"
        and data["memory"]["auto_save"]
    )
    assert (
        data["search"]["roles"] == {"search": ["exa", "searxng"]}
        and not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()
    )
    path.write_text(
        path.read_text().replace('stt_provider = "evoice-stt:parakeet"', 'stt_provider = "cloud:whisper"', 1)
    )
    assert [str(d) for d in Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()] == [
        "memory/openhuman/users/p/config.toml: drift"
    ]


async def test_render_export_makes_an_owned_symlinked_file_real(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    target = next(path for path in render.files if path.name == "config.toml")
    elsewhere = tmp_path / "elsewhere.toml"
    elsewhere.write_text("untouched = true\n")
    target.parent.mkdir(parents=True)
    target.symlink_to(elsewhere)
    assert any("symlink" in str(d) for d in render.check())
    render.export()
    assert not target.is_symlink() and elsewhere.read_text() == "untouched = true\n"


async def test_render_toml_reaches_exa_like_opencode(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    servers = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["mcp_client"]["servers"]
    assert {"name": "exa", "enabled": True, "endpoint": "https://mcp.exa.ai/mcp"} in servers


async def test_render_toml_oauth_server_written_disabled(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    servers = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["mcp_client"]["servers"]
    assert {"name": "e-metaxy", "enabled": False, "endpoint": "http://127.0.0.1:45190/mcp"} in servers


async def test_render_toml_pinned_server_sent_every_turn(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    client = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["mcp_client"]
    assert client["direct_servers"] == ["e-metaxy"]


async def test_render_toml_export_disables_a_live_oauth_server_in_place(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[[mcp_client.servers]]\nname = "e-metaxy"\nendpoint = "http://127.0.0.1:45190/mcp"\nenabled = true\n'
        "timeout_secs = 60\n"
    )
    render.export()
    metaxy = next(s for s in tomllib.loads(path.read_text())["mcp_client"]["servers"] if s["name"] == "e-metaxy")
    assert (metaxy["enabled"], metaxy["timeout_secs"]) == (False, 60)
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_export_keeps_an_mcp_server_the_app_added(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[mcp_client]\nenabled = true\n[[mcp_client.servers]]\nname = "mine"\nendpoint = "https://x/mcp"\nenabled = true\n'
    )
    render.export()
    names = [s["name"] for s in tomllib.loads(path.read_text())["mcp_client"]["servers"]]
    assert names == ["e-metaxy", "exa", "context7", "mine"]
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_one_vault_declaration_feeds_both_permission_systems(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    data = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])
    vault = str(tmp_path / "memory")
    roots = {r["path"]: r["access"] for r in data["autonomy"]["trusted_roots"]}
    jail = data["runtime"]["local_jail"]
    assert roots == {
        **{f"{vault}/{d}": "read" for d in ("persona", "wiki", "brain")},
        **{f"{vault}/{d}": "readwrite" for d in ("workflow", "inbox")},
    }
    assert (
        jail["extra_read_only"][:3] == [f"{vault}/{d}" for d in ("persona", "wiki", "brain")]
        and "~/.local/bin" in jail["extra_read_only"]
        and set(jail["extra_read_write"]) == {p for p, a in roots.items() if a == "readwrite"}
    )
    assert all(s["schedule_mins"] for s in data["memory"]["sources"]) and data["update"]["enabled"] is False


async def test_render_toml_memory_runs_on_the_local_engine(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    memory = tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["memory"]
    assert memory["engine"] == "cortexdb" and memory["engines"]["cortexdb"]["endpoint"].startswith("http://127.0.0.1:")
    assert "api_key" not in memory["engines"]["cortexdb"]


async def test_render_toml_export_updates_an_item_field_by_field(tmp_path: Path) -> None:
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    path = tmp_path / "memory/openhuman/users/p/config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[[mcp_client.servers]]\nname = "exa"\nendpoint = "https://old/mcp"\ntimeout_secs = 45\n')
    render.export()
    exa = next(s for s in tomllib.loads(path.read_text())["mcp_client"]["servers"] if s["name"] == "exa")
    assert exa["endpoint"] == "https://mcp.exa.ai/mcp" and exa["timeout_secs"] == 45
    assert not Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").check()


async def test_render_toml_a_source_switched_off_stays_declared_and_is_not_ingested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Transpiler._CONFIG[Backend.OPENHUMAN]

    def with_off(self: Transpiler, mods: dict) -> dict:
        sources = mods["sources"] | {"old": {"id": "kb_old", "label": "o", "path": "old", "glob": "*", "off": True}}
        return real(self, mods | {"sources": sources})

    monkeypatch.setitem(Transpiler._CONFIG, Backend.OPENHUMAN, with_off)
    render = Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p")
    ids = [
        s["id"]
        for s in tomllib.loads(render.files[tmp_path / "memory/openhuman/users/p/config.toml"])["memory"]["sources"]
    ]
    assert "kb_old" not in ids and {"src_vault_notes", "kb_wiki", "kb_workflow"} <= set(ids)


async def test_render_toml_tool_calls_are_native(tmp_path: Path) -> None:
    data = tomllib.loads(
        Transpiler(settings.ROOT, Backend.OPENHUMAN, tmp_path, "p").files[
            tmp_path / "memory/openhuman/users/p/config.toml"
        ]
    )
    assert data["agent"]["tool_dispatcher"] == "native"
