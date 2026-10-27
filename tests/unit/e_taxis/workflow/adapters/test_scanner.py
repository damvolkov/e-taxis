"""tests/unit/e_taxis/workflow/adapters/scanner: SkillSpector's JSON decoded into house findings — the pinned argv,
fingerprints derived when absent, duplicates of one place folded."""

from pathlib import Path
from typing import TYPE_CHECKING

from e_taxis.workflow.adapters.scanner import SkillspectorScanner

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
