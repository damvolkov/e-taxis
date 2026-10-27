"""tests/unit/e_taxis/workflow/adapters/coder: each coder read off its own event stream — the skills its skill tool
loaded, the references any tool named, its text, every billed token — and pointed at a sandbox around the render,
never the live tree."""

from pathlib import Path

import msgspec
import pytest

from e_taxis.workflow.adapters.coder import ClaudeCoder, OpencodeCoder
from e_taxis.workflow.models.case import ProbeMode, ProbeResult

OPENCODE = "\n".join(
    msgspec.json.encode(event).decode()
    for event in (
        {"part": {"type": "tool", "tool": "skill", "state": {"input": {"name": "algo-py-core"}}}},
        {
            "part": {
                "type": "tool",
                "tool": "read",
                "state": {"input": {"path": "/x/skills/algo-py-core/references/a.md"}},
            }
        },
        {"part": {"type": "text", "text": "done"}},
        {"part": {"type": "step-finish", "tokens": {"total": 40}}},
        {"part": {"type": "step-start"}},
    )
)
CLAUDE = "\n".join(
    [
        "not json",
        *(
            msgspec.json.encode(event).decode()
            for event in (
                {"type": "system", "subtype": "init"},
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Skill", "input": {"skill": "algo-py-core"}},
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/h/skills/algo-py-core/references/b.md"},
                            },
                            {"type": "text", "text": "done"},
                            {"type": "thinking", "thinking": "hm"},
                        ]
                    },
                },
                {"type": "result", "usage": {"input_tokens": 3, "cache_read_input_tokens": 100, "output_tokens": 2}},
            )
        ),
    ]
)
SEEN = ProbeResult(
    loaded=frozenset({"algo-py-core"}),
    opened=frozenset({"algo-py-core/a.md"}),
    text="done",
    tokens=40,
)


async def test_coder_opencode_read() -> None:
    assert OpencodeCoder.read(OPENCODE) == SEEN


async def test_coder_claude_read() -> None:
    assert ClaudeCoder.read(CLAUDE) == ProbeResult(
        loaded=frozenset({"algo-py-core"}), opened=frozenset({"algo-py-core/b.md"}), text="done", tokens=105
    )


async def test_coder_opencode_sandbox_replaces_only_its_config(tmp_path: Path, fake_command) -> None:
    real, flat, root = tmp_path / "config", tmp_path / "flat", tmp_path / "xdg"
    (real / "opencode").mkdir(parents=True)
    (real / "git").mkdir()
    flat.mkdir()
    env = await OpencodeCoder(fake_command, real).sandbox(flat, root)
    assert ((root / "opencode").resolve(), (root / "git").resolve()) == (flat, real / "git")
    assert env == {
        "XDG_CONFIG_HOME": str(root),
        "OPENCODE_CONFIG_DIR": str(flat),
        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
        "OPS_GLOBAL__HEADLESS": "1",
    }


@pytest.mark.parametrize("signed", [True, False], ids=["signed-in", "bare"])
async def test_coder_claude_sandbox_borrows_the_credentials(tmp_path: Path, fake_command, signed: bool) -> None:
    real, flat, root = tmp_path / "home" / ".claude", tmp_path / "flat", tmp_path / "sandbox"
    real.mkdir(parents=True)
    (flat / "skills").mkdir(parents=True)
    _ = signed and (real / ".credentials.json").write_text("{}")
    _ = signed and (real.parent / ".claude.json").write_text('{"n": 1}')
    env = await ClaudeCoder(fake_command, real).sandbox(flat, root)
    assert (root / "skills").resolve() == flat / "skills"
    assert ((root / ".credentials.json").is_symlink(), (root / ".claude.json").is_file()) == (signed, signed)
    assert env == {"CLAUDE_CONFIG_DIR": str(root), "OPS_GLOBAL__HEADLESS": "1"}


async def test_coder_opencode_probe(fake_command, tmp_path: Path) -> None:
    fake_command.answers[("opencode",)] = OPENCODE
    result = await OpencodeCoder(fake_command, tmp_path).probe("-sort it", ProbeMode.PRELOAD, env={"A": "1"}, limit=9.0)
    ((argv, env),) = fake_command.calls
    assert argv[:6] == ("opencode", "run", "--agent", "plan", "--format", "json")
    assert (len(argv), argv[6].endswith("\n\n-sort it"), env) == (7, True, {"A": "1"})
    assert result == SEEN


async def test_coder_claude_probe(fake_command, tmp_path: Path) -> None:
    fake_command.answers[("claude",)] = CLAUDE
    await ClaudeCoder(fake_command, tmp_path).probe("-sort it", ProbeMode.NAVIGATION, env={}, limit=9.0)
    ((argv, _),) = fake_command.calls
    assert (argv[0], argv[-2:], argv[argv.index("--max-turns") + 1]) == ("claude", ("--", "-sort it"), "8")


async def test_coder_claude_sandbox_links_resolve_from_a_relative_render(
    tmp_path: Path, fake_command, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    real, root = tmp_path / "home" / ".claude", tmp_path / "run" / "home"
    real.mkdir(parents=True)
    (tmp_path / "run" / "flat" / "skills").mkdir(parents=True)
    await ClaudeCoder(fake_command, real).sandbox(Path("run/flat"), root)
    assert (root / "skills").is_dir()


async def test_coder_opencode_sandbox_links_resolve_from_a_relative_render(
    tmp_path: Path, fake_command, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    real, root = tmp_path / "xdg", tmp_path / "run" / "home"
    real.mkdir()
    (tmp_path / "run" / "flat" / "skills").mkdir(parents=True)
    await OpencodeCoder(fake_command, real).sandbox(Path("run/flat"), root)
    assert (root / "opencode" / "skills").is_dir()


@pytest.mark.parametrize("key", ["name", "id"], ids=["opencode-1", "opencode-2"])
async def test_coder_opencode_reads_the_skill_by_either_key(key: str) -> None:
    event = {"part": {"type": "tool", "tool": "skill", "state": {"input": {key: "para-py-dispatch"}}}}
    assert OpencodeCoder.read(msgspec.json.encode(event).decode()).loaded == frozenset({"para-py-dispatch"})
