"""The hermes config: core/nomos/config rendered to config.yaml by dotted path and .env by key — Hermes's own leaves untouched."""

from __future__ import annotations

from pathlib import Path

import eserde

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.transpiler.render import Transpiler


def config_of(tree: Path) -> dict:
    return eserde.loads((tree / "config.yaml").read_text(), format=eserde.Format.YAML)


async def test_render_hermes_routes_roles_through_named_providers(tmp_path: Path) -> None:
    data = eserde.loads(
        Transpiler(settings.ROOT, Backend.HERMES, tmp_path).files[tmp_path / "config.yaml"], format=eserde.Format.YAML
    )
    alibaba = data["providers"]["nomos-alibaba"]
    assert data["model"] == {"provider": "nomos-alibaba", "default": "deepseek-v4.1-flash"}
    assert alibaba["api_mode"] == "anthropic_messages" and alibaba["key_env"] == "ALIBABA_API_KEY"
    assert data["auxiliary"]["compression"]["provider"] == "nomos-vllm" and data["agent"]["max_turns"] == "none"
    assert data["terminal"]["cwd"] == str(tmp_path / "workspace") and data["context_file_max_chars"] >= 60000


async def test_render_hermes_persona_fits_its_cap(tmp_path: Path) -> None:
    files = Transpiler(settings.ROOT, Backend.HERMES, tmp_path).files
    soul, agents = files[tmp_path / "SOUL.md"], files[tmp_path / "workspace/AGENTS.md"]
    assert 20_000 < len(soul) <= 60_000 and "## Mission" in soul and "## Voice" in soul
    assert "## Craft" in agents and "## Modes" in agents


async def test_render_hermes_env_keeps_secrets_byte_for_byte(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('# keys\nALIBABA_API_KEY="sk-secret=x"\nDISCORD_ALLOWED_USERS=old\nDISCORD_BOT_TOKEN=tok\n')
    Transpiler(settings.ROOT, Backend.HERMES, tmp_path).export()
    lines = env.read_text().splitlines()
    assert lines[:2] == ["# keys", 'ALIBABA_API_KEY="sk-secret=x"'] and "DISCORD_BOT_TOKEN=tok" in lines
    assert "DISCORD_ALLOWED_USERS=1483749257545515048" in lines and "SEARXNG_URL=http://localhost:45600" in lines
    assert not Transpiler(settings.ROOT, Backend.HERMES, tmp_path).check()


async def test_render_hermes_keeps_the_users_own_providers(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "_config_version: 50\nproviders:\n  mine:\n    base_url: http://x/v1\nmodel:\n  provider: old\n"
    )
    Transpiler(settings.ROOT, Backend.HERMES, tmp_path).export()
    data = config_of(tmp_path)
    assert set(data["providers"]) == {"mine", "nomos-alibaba", "nomos-vllm"} and data["_config_version"] == 50
    assert data["model"]["provider"] == "nomos-alibaba"
    assert not Transpiler(settings.ROOT, Backend.HERMES, tmp_path).check()
