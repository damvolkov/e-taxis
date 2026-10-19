"""tests/unit/e_taxis/adapters/core: an e-engineer core read into the contract — from HEAD by git archive, or from the
working tree; bodies embedded, envelopes lifted, every broken input a CoreError."""

import shutil
from typing import TYPE_CHECKING

import anyio
import pytest

from e_taxis.adapters.core import GitCore
from e_taxis.models.core import CoreHook, CoreServer
from e_taxis.models.error import CoreError

if TYPE_CHECKING:
    from pathlib import Path


async def test_core_worktree_reads_every_entity_with_bodies_embedded(core_root: Path) -> None:
    core = await GitCore(core_root, None).load()
    assert core.persona["unity"] == "Code and word.\n"
    assert core.persona["origin"] == "\nDamien builds.\n\n"
    assert core.skills["demo"].instructions == "## Rules\n\n1. One.\n\n"
    assert core.references == {"demo": {"references/a.md": b"Reference A.\n"}}
    assert (core.agents["scout"].prompt, core.agents["scout"].max_steps) == ("You are the scout.\n", 12)
    assert list(core.commands["ask"].inputs) == ["topic", "depth"]
    assert core.main.model.alias == {"claudecode": "opus"}
    assert core.permissions.rules.allow == ("Bash(*)", "WebSearch")
    assert core.hooks["Stop"] == (CoreHook(run=("node", "{out}/hooks/remind", "stop")),)
    assert core.mcp.servers["remote"] == CoreServer(url="https://mcp.example.com/mcp")
    assert sorted(core.carried) == ["hooks/remind", "mcp/pw.json"]


async def test_core_config_is_data_where_a_source_key_means_what_it_says(core_root: Path) -> None:
    ### mcp.yaml's smoke carries `source: https://…`; embedding it would refuse the file.
    core = await GitCore(core_root, None).load()
    assert "local" in core.mcp.servers


async def test_core_head_reads_the_commit_not_the_working_tree(core_repo: Path) -> None:
    (core_repo / "core/engineer/persona/origin.md").write_text("uncommitted\n")
    core = await GitCore(core_repo).load()
    assert core.persona["origin"] == "\nDamien builds.\n\n"


async def test_core_unknown_ref_is_refused(core_repo: Path) -> None:
    with pytest.raises(CoreError, match="git archive nope"):
        await GitCore(core_repo, "nope").load()


async def test_core_slot_in_two_layers_is_refused(core_root: Path, tmp_path: Path) -> None:
    root = shutil.copytree(core_root, tmp_path / "twice")
    persona = root / "core/engineer/persona.yaml"
    persona.write_text(persona.read_text() + "  name: Twice\n")
    with pytest.raises(CoreError, match="more than one layer: name"):
        await GitCore(root, None).load()


async def test_core_manifest_off_contract_is_refused(core_root: Path, tmp_path: Path) -> None:
    root = shutil.copytree(core_root, tmp_path / "off")
    (root / "core/engineer/agents/scout/agent.yaml").write_text("id: scout\n")
    with pytest.raises(CoreError, match=r"agent\.yaml"):
        await GitCore(root, None).load()


async def test_core_server_with_command_and_url_is_refused(core_root: Path, tmp_path: Path) -> None:
    root = shutil.copytree(core_root, tmp_path / "both")
    (root / "core/engineer/config/mcp.yaml").write_text("servers:\n  x: {command: [a], url: 'https://b'}\n")
    with pytest.raises(CoreError, match="exactly one"):
        await GitCore(root, None).load()


async def test_core_missing_reference_is_refused(core_root: Path, tmp_path: Path) -> None:
    root = shutil.copytree(core_root, tmp_path / "noref")
    (root / "core/engineer/skills/demo/references/a.md").unlink()
    with pytest.raises(CoreError, match="reference it does not ship"):
        await GitCore(root, None).load()


async def test_core_not_a_checkout_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreError, match=r"persona\.yaml"):
        await GitCore(tmp_path, None).load()
    await anyio.run_process(("git", "-C", str(tmp_path), "init", "-q"))
    with pytest.raises(CoreError, match="exited"):
        await GitCore(tmp_path).load()
