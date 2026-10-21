"""tests/unit/e_taxis/adapters/harness/claudecode: where every slot of the core lands in Claude Code's tree — exact
bytes for the flat files, owned settings keys in order, registrations in the shape Claude stores them."""

from pathlib import Path
from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.adapters.core import GitCore
from e_taxis.adapters.harness.claudecode import ClaudecodeHarness
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.core import Core, CoreMain, CoreModel
from e_taxis.harness.models.error import CoreError

if TYPE_CHECKING:
    from e_taxis.harness.models.brain import BrainRender

TREE = Path("/tree")


@pytest.fixture
async def core(core_root: Path) -> Core:
    return await GitCore(core_root, None).load()


@pytest.fixture
def render(core: Core) -> BrainRender:
    return ClaudecodeHarness().render(core, TREE)


def _file(render: BrainRender, path: str) -> str:
    return next(file.data.decode() for file in render.files if file.path == path)


def test_claudecode_files_land_where_claude_reads_them(render: BrainRender) -> None:
    assert [file.path for file in render.files] == [
        "skills/demo/SKILL.md",
        "skills/demo/references/a.md",
        "agents/scout.md",
        "commands/ask.md",
        "CLAUDE.md",
        "rules/instructions.md",
        "hooks/remind",
        "mcp/pw.json",
    ]
    assert (render.target, render.governed) == (Target.CLAUDECODE, ("skills", "agents", "commands"))


def test_claudecode_skill_is_frontmatter_title_and_body(render: BrainRender) -> None:
    assert _file(render, "skills/demo/SKILL.md") == (
        '---\nname: demo\ndescription: "Demo: a skill for tests. Use when testing."\nmetadata:\n  family: test\n---\n\n'
        "# demo\n\n## Rules\n\n1. One.\n"
    )
    assert _file(render, "skills/demo/references/a.md") == "Reference A.\n"


def test_claudecode_agent_denies_only_tools_the_house_denies_outright(render: BrainRender) -> None:
    ### `skill` allows one skill: a pattern grant has no tool-level twin, so Skill stays allowed.
    assert _file(render, "agents/scout.md") == (
        "---\nname: scout\ndescription: Reads, never writes.\nskills:\n- demo\nmaxTurns: 12\ndisallowedTools:\n"
        "- Bash\n- Edit\n- Write\n- NotebookEdit\n---\n\nYou are the scout.\n"
    )


def test_claudecode_command_names_its_arguments(render: BrainRender) -> None:
    assert _file(render, "commands/ask.md") == (
        '---\ndescription: Ask about a topic.\narguments:\n- topic\n- depth\nargument-hint: "[topic] [depth]"\n---\n\n'
        "Tell me about $topic at $depth, not $HOME.\n"
    )


def test_claudecode_persona_is_blocks_in_order_empty_slots_skipped(render: BrainRender) -> None:
    text = _file(render, "CLAUDE.md")
    assert text.startswith("# Demo\n\nThe essence.\n\n> A quote.\n\n## Damien\n\nDamien builds.\n\n## One mind")
    assert "## Temperament" not in text
    assert "## Philosophy and logic\n\nStance line.\nReason well.\n\n## Voice" in text
    assert text.endswith("## Skills\n\nSkills.")
    assert "Not for coders" not in text
    persona = next(file for file in render.files if file.path == "CLAUDE.md")
    assert persona.headings is not None
    assert "Temperament" in persona.headings


def test_claudecode_persona_slot_no_layer_declares_is_refused(core: Core) -> None:
    broken = msgspec.structs.replace(core, persona={k: v for k, v in core.persona.items() if k != "honesty"})
    with pytest.raises(CoreError, match="honesty"):
        ClaudecodeHarness().render(broken, TREE)


def test_claudecode_instructions_bind_the_tree(render: BrainRender) -> None:
    assert _file(render, "rules/instructions.md") == "@~/notes.md\n@/tree/skills/demo/SKILL.md\n"


def test_claudecode_settings_keys_in_order(render: BrainRender) -> None:
    owned = {key.key: key.value for key in render.keys}
    assert list(owned) == ["$schema", "model", "effortLevel", "tui", "permissions", "hooks"]
    assert {key.file for key in render.keys} == {"settings.json"}
    assert (owned["model"], owned["effortLevel"], owned["tui"]) == ("opus", "high", "fullscreen")
    assert owned["permissions"] == {
        "allow": ["Bash(*)", "WebSearch"],
        "defaultMode": "auto",
        "additionalDirectories": ["/srv/shared"],
    }
    assert owned["hooks"] == {
        "SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": "bash /tree/hooks/remind"}]},
            {"matcher": "resume", "hooks": [{"type": "command", "command": "bash /tree/hooks/remind"}]},
        ],
        "Stop": [{"hooks": [{"type": "command", "command": "node /tree/hooks/remind stop"}]}],
    }


def test_claudecode_model_without_a_claudecode_alias_is_refused(core: Core) -> None:
    broken = msgspec.structs.replace(core, main=CoreMain(model=CoreModel(alias={"opencode": "x"})))
    with pytest.raises(CoreError, match="claudecode"):
        ClaudecodeHarness().render(broken, TREE)


def test_claudecode_servers_enabled_for_claude_in_its_shape(render: BrainRender) -> None:
    assert {server.name: server.config for server in render.servers} == {
        "local": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "local-mcp"],
            "env": {"CONFIG": "/tree/mcp/pw.json"},
        },
        "remote": {"type": "http", "url": "https://mcp.example.com/mcp"},
        "bare": {"type": "stdio", "command": "bare-mcp", "args": []},
    }
