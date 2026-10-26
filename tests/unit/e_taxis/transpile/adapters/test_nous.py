"""tests/unit/e_taxis/transpile/adapters/nous: a checkout read whole — at a ref or as it stands, envelopes resolved."""

from typing import TYPE_CHECKING

import anyio
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.error import NousError

if TYPE_CHECKING:
    from pathlib import Path


async def test_nous_worktree_resolves_markdown_and_yaml_sources(nous_root: Path) -> None:
    tree = await GitNous(nous_root, None).load()
    workflow = tree.entities["workflow"]["converge"]
    assert isinstance(tree.entities["skill"]["algo-py-core"]["instructions"], str)
    assert isinstance(tree.persona["base"]["slots"]["unity"], str)
    assert {node["id"] for node in workflow["nodes"]} >= {"guard", "evaluate"}
    assert tree.commit == "worktree"


async def test_nous_worktree_lists_specs_entities_config_and_assets(nous_root: Path) -> None:
    tree = await GitNous(nous_root, None).load()
    assert sorted(tree.specs) == ["nomos/hermes", "nomos/openhuman", "tekton/claudecode", "tekton/opencode"]
    assert {entity: len(found) for entity, found in tree.entities.items()} == {
        "skill": 1,
        "agent": 1,
        "command": 1,
        "workflow": 1,
    }
    assert {"main", "mcp", "telemetry"} <= set(tree.config["tekton"])
    assert "mcp/playwright.json" in tree.assets["tekton"]


async def test_nous_ref_reads_the_commit_not_the_worktree(nous_git: Path) -> None:
    (nous_git / "core/base/persona/self/unity.md").write_text("uncommitted\n")
    tree = await GitNous(nous_git, "HEAD").load()
    head = (await anyio.run_process(("git", "-C", str(nous_git), "rev-parse", "HEAD"))).stdout.decode().strip()
    assert tree.commit == head
    assert tree.persona["base"]["slots"]["unity"] != "uncommitted\n"


async def test_nous_unknown_ref_is_a_nous_error(nous_git: Path) -> None:
    with pytest.raises(NousError, match="rev-parse"):
        await GitNous(nous_git, "no-such-ref").load()


async def test_nous_source_escaping_its_folder_is_refused(nous_root: Path) -> None:
    manifest = nous_root / "core/tekton/skills/algo-py-core/skill.yaml"
    manifest.write_text(manifest.read_text().replace("{source: instructions.md}", "{source: ../../persona.yaml}"))
    with pytest.raises(NousError, match="escapes"):
        await GitNous(nous_root, None).load()


async def test_nous_unparsable_yaml_is_a_nous_error(nous_root: Path) -> None:
    (nous_root / "specs/nomos/hermes.yaml").write_text("a: [\n")
    with pytest.raises(NousError, match=r"hermes\.yaml"):
        await GitNous(nous_root, None).load()


async def test_nous_source_of_another_kind_is_refused(nous_root: Path) -> None:
    folder = nous_root / "core/tekton/skills/algo-py-core"
    (folder / "body.txt").write_text("plain\n")
    manifest = folder / "skill.yaml"
    manifest.write_text(manifest.read_text().replace("{source: instructions.md}", "{source: body.txt}"))
    with pytest.raises(NousError, match="Markdown or YAML"):
        await GitNous(nous_root, None).load()
