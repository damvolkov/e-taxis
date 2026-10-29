"""tests/unit/e_taxis/workflow/compare/intake: a repository's declared stack — manifests, versions, scopes, imports."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.compare.intake import CompareIntake, image_parts, locked_npm, modules_record
from e_taxis.workflow.models.error import CompareError

if TYPE_CHECKING:
    from pathlib import Path

ROWS = {
    "msgspec": ("python", "", ">=0.21", "0.22.0", ("src/app/main.py",)),
    "wreq": ("python", "", ">=0.10", "0.12.2", ("src/app/http.py",)),
    "orjson": ("python", "optional:fast", ">=3", "", ()),
    "pytest": ("python", "group:dev", ">=8", "7.4.4, 8.4.0", ()),
    "serde": ("rust", "", "1", "1.0.200", ("src/lib.rs",)),
    "local": ("rust", "", "path ../local", "", ()),
    "shared": ("rust", "", "workspace", "", ()),
    "cc": ("rust", "build", "git https://github.com/rust-lang/cc-rs", "", ()),
    "anyhow": ("rust", "workspace", "1", "", ("src/lib.rs",)),
    "@scope/ui": ("js", "", "^1.0.0", "1.2.0", ("web/index.ts",)),
    "vite": ("js", "dev", "^5.0.0", "", ("web/index.ts",)),
    "ghcr.io/caddy/caddy": ("container", "service:proxy", "2.8@sha256:abc123", "", ()),
    "redis": ("container", "service:cache", "", "", ()),
}


async def test_intake_reads_every_manifest(project: Path) -> None:
    stack = await CompareIntake(("memory",)).read(project, "is there better?", "memory")
    rows = {dep.name: (dep.ecosystem, dep.scope, dep.declared, dep.resolved, dep.imports) for dep in stack.dependencies}
    assert {name: rows[name] for name in ROWS} == ROWS
    assert (stack.query, stack.topic, stack.manifests[:2]) == (
        "is there better?",
        "memory",
        ("pyproject.toml", "uv.lock"),
    )


async def test_intake_reads_a_distribution_s_modules_from_the_venv(project: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["e-serde>=0.5"]\n')
    (repo / "src" / "a.py").write_text("import eserde\n")
    dist = repo / ".venv" / "lib" / "python3.14" / "site-packages" / "e_serde-0.5.1.dist-info"
    dist.mkdir(parents=True)
    (dist / "top_level.txt").write_text("eserde\n")
    stack = await CompareIntake(()).read(repo, "q")
    assert stack.dependencies[0].imports == ("src/a.py",)


@pytest.mark.parametrize(
    ("setup", "topic", "match"),
    [
        ("missing", "", "no such directory"),
        ("empty", "", "declares no dependency"),
        ("empty", "cooking", "topic 'cooking'"),
    ],
    ids=["missing", "empty", "topic"],
)
async def test_intake_refuses(tmp_path: Path, setup: str, topic: str, match: str) -> None:
    folder = tmp_path / setup
    _ = setup == "empty" and folder.mkdir()
    with pytest.raises(CompareError, match=match):
        await CompareIntake(("memory",)).read(folder, "q", topic)


@pytest.mark.parametrize(
    ("image", "parts"),
    [
        ("postgres:16-alpine", ("postgres", "16-alpine")),
        ("localhost:5000/tool", ("localhost:5000/tool", "")),
        ("repo/app@sha256:ff", ("repo/app", "sha256:ff")),
    ],
    ids=["tag", "port-no-tag", "digest"],
)
async def test_intake_image_parts(image: str, parts: tuple[str, str]) -> None:
    assert image_parts(image) == parts


async def test_intake_locked_npm_v1_is_flat() -> None:
    assert locked_npm({"dependencies": {"lodash": {"version": "4.0.0"}}}) == {"lodash": "4.0.0"}


@pytest.mark.parametrize(
    ("files", "modules"),
    [
        ({"top_level.txt": "a\nb\n"}, ("a", "b")),
        ({"RECORD": "pkg/__init__.py,,\npkg.pth,,\n__pycache__/x,,\nx-1.0.dist-info/METADATA,,\n"}, ("pkg",)),
        ({}, ()),
    ],
    ids=["top-level", "record", "nothing"],
)
async def test_intake_modules_record(tmp_path: Path, files: dict[str, str], modules: tuple[str, ...]) -> None:
    _ = [(tmp_path / name).write_text(text) for name, text in files.items()]
    assert modules_record(tmp_path) == modules
