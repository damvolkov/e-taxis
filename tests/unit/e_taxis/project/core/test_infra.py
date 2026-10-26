"""Where assemble lands each library file: CI-only tooling under .github/tools, contracts at their fixed homes."""

from e_taxis.project.core.infra import Library, assemble
from e_taxis.project.models.infra import Feature, FeatureMap

LIBRARY = Library(
    map=FeatureMap(
        version=1,
        features={
            "selfmaintain": Feature(
                label="renovate and friends",
                jobs={},
                files=("renovate.json", "qwen.md", "tools/health.py", "tools/upstream.py"),
            ),
        },
    ),
    fragments={
        "workflows/ci.yml": "jobs:\n{{ci_jobs}}",
        "workflows/release.yml": "jobs:\n{{release_jobs}}",
        "triggers/dispatch.yml": "workflow_dispatch:",
        "files/renovate.json": "{}",
        "files/qwen.md": "contract",
        "files/tools/health.py": "print()",
        "files/tools/upstream.py": "print()",
        "contract.py.j2": "assert True",
    },
)


def test_assemble_tools_land_under_github() -> None:
    files = assemble(LIBRARY, {}, frozenset({"selfmaintain"}))
    assert ".github/tools/health.py" in files
    assert ".github/tools/upstream.py" in files
    assert not any(key.startswith("tools/") for key in files)


def test_assemble_contracts_keep_their_homes() -> None:
    files = assemble(LIBRARY, {}, frozenset({"selfmaintain"}))
    assert ".github/renovate.json" in files
    assert "QWEN.md" in files
