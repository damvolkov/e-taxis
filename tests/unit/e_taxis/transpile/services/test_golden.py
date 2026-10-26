"""tests/unit/e_taxis/transpile/services/golden: acceptance — the render equals the v1 transpiler's, byte for byte.

The fixture core is a slice of e-nous; every file it renders that v1 rendered too must match v1's golden render,
`{out}` aside. The files v2 changes on purpose are named, each with its reason, and compared on what they keep."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from pathlib import Path

### v2 on purpose: total ownership models every settings key; #81 retired the reminder hook and tree-sitter, pinned
### Serena and guided codebase-memory in OpenCode only; the fixture holds four instances, not the corpus.
CHANGED = {"settings.json", "opencode.jsonc"}
### where v1 rendered the golden: its `{out}`, replaced on both sides before comparing.
GOLDEN_OUT = "/tmp/e-nous-golden-v1"  # noqa: S108 — a recorded path inside fixture bytes, never written to


@pytest.mark.parametrize("backend", ["claudecode", "opencode"])
async def test_golden_files_match_byte_for_byte(
    nous_root: Path, tmp_path: Path, golden_root: Path, backend: str
) -> None:
    out = tmp_path / backend
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), backend, out)
    golden = golden_root / backend
    shared = [path for path in projection.files if (golden / path).is_file() and path not in CHANGED]
    mismatched = [
        path
        for path in shared
        if (golden / path).read_bytes().replace(f"{GOLDEN_OUT}/{backend}".encode(), b"OUT")
        != projection.files[path].replace(str(out).encode(), b"OUT")
    ]
    assert len(shared) >= 10
    assert mismatched == []


async def test_golden_settings_keep_every_v1_key(nous_root: Path, tmp_path: Path, golden_root: Path) -> None:
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), "claudecode", tmp_path / "cc")
    golden = msgspec.json.decode((golden_root / "claudecode/settings.json").read_bytes())
    rendered = msgspec.json.decode(projection.files["settings.json"])
    assert [key for key in golden if key != "hooks"] == [key for key in rendered if key in golden and key != "hooks"]
    assert all(rendered[key] == golden[key] for key in ("model", "effortLevel", "tui", "permissions"))
    assert {"env", "enabledPlugins"} <= set(rendered)


@pytest.mark.parametrize(
    ("backend", "tree", "files"),
    [
        ("hermes", ".hermes", ["SOUL.md", "workspace/AGENTS.md", "memories/USER.md", ".env"]),
        (
            "openhuman",
            ".config",
            [
                "memory/persona/SOUL.md",
                "memory/persona/IDENTITY.md",
                "memory/persona/ROLE.md",
                "memory/persona/STYLE.md",
                "memory/persona/PROFILE.md",
            ],
        ),
    ],
    ids=["hermes", "openhuman"],
)
async def test_golden_nomos_documents_match(
    nous_root: Path, tmp_path: Path, golden_root: Path, backend: str, tree: str, files: list[str]
) -> None:
    live = tmp_path / "live" / tree
    (live / "memory/openhuman").mkdir(parents=True)
    (live / "memory/openhuman/active_user.toml").write_text('user_id = "6abd6edb6e176e3e56822476"\n')
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), backend, tmp_path / backend, live=live)
    assert {path: projection.files[path] for path in files} == {
        path: (golden_root / backend / path).read_bytes() for path in files
    }
