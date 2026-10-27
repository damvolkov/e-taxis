"""tests/unit/e_taxis/workflow/adapters/scanner: SkillSpector's JSON decoded into house findings — the pinned argv,
fingerprints derived when absent, duplicates of one place folded; the LLM stage on the provider's OpenAI twin, its
key in the environment only."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.adapters.scanner import SkillspectorScanner
from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.error import ProviderError

if TYPE_CHECKING:
    from pytest_resources import Resources

SOURCE = "git+https://github.com/NVIDIA/SkillSpector@v2.12.0"


async def test_scanner_decodes_the_report(fake_command, resources: Resources) -> None:
    fake_command.answers[("uvx",)] = (resources.path / "plane" / "spector.json").read_text()
    result = await SkillspectorScanner(fake_command, 60.0).scan(Path("/flat/skills/x"), SOURCE)
    ((argv, _),) = fake_command.calls
    assert argv == (
        "uvx",
        "-q",
        "--from",
        SOURCE,
        "skillspector",
        "scan",
        "/flat/skills/x",
        "--no-llm",
        "--format",
        "json",
    )
    assert (result.scanner, result.score) == ("skillspector@v2.12.0", 42)
    assert [(f.rule, f.path, f.line) for f in result.findings] == [
        ("E1", "SKILL.md", 9),
        ("R2", "references/lib.md", 3),
        ("N3", "", 0),
    ]
    folded, derived, bare = result.findings
    ### the same place twice is one finding: the later issue stands, its fingerprint derived from rule and snippet.
    assert folded.detail == "duplicate of the same place"
    assert len(folded.fingerprint) == len(derived.fingerprint) == 64
    assert (bare.severity, bare.detail) == ("LOW", "")


async def test_scanner_llm_stage_on_the_openai_twin(fake_command, resources: Resources) -> None:
    fake_command.answers[("uvx",)] = (resources.path / "plane" / "spector.json").read_text()
    llm = Endpoint(base_url="https://m/v1", key="sk-secret", model="qwen", openai_url="https://m/compat/v1")
    result = await SkillspectorScanner(fake_command, 60.0).scan(Path("/flat/skills/x"), SOURCE, llm)
    ((argv, env),) = fake_command.calls
    assert "--no-llm" not in argv
    assert "sk-secret" not in " ".join(argv)
    assert env == {
        "SKILLSPECTOR_PROVIDER": "openai_compatible",
        "SKILLSPECTOR_COMPAT_BASE_URL": "https://m/compat/v1",
        "SKILLSPECTOR_COMPAT_API_KEY": "sk-secret",
        "SKILLSPECTOR_MODEL": "qwen",
    }
    assert result.scanner == "skillspector@v2.12.0+llm:qwen"


async def test_scanner_llm_stage_needs_an_openai_twin(fake_command) -> None:
    llm = Endpoint(base_url="https://m/v1", key="k", model="qwen")
    with pytest.raises(ProviderError, match="no openai_url"):
        await SkillspectorScanner(fake_command, 60.0).scan(Path("/flat/skills/x"), SOURCE, llm)
    assert fake_command.calls == []
