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
    from collections.abc import Callable
    from pathlib import Path

### v2 on purpose: total ownership models every settings key; #81 retired the reminder hook and tree-sitter, pinned
### Serena and guided codebase-memory in OpenCode only; the fixture holds four instances, not the corpus.
CHANGED = {"settings.json", "opencode.jsonc"}
### v2 on purpose (2026-10-28): a workflow's steps go through `taxis workflow step` and `put`, walked in the foreground.
WALKED = {f"workflows/{ident}.md" for ident in ("converge", "emaintenance", "reverse-distill", "smaintenance")}
### v2 adds ## Plans, ## Agents (2026-10-27) and renamed ## The three pillars ## The Triad (2026-10-28): cut on both sides.
PERSONA = {"CLAUDE.md", "AGENTS.md"}
### where v1 rendered the golden: its `{out}`, replaced on both sides before comparing.
GOLDEN_OUT = "/tmp/e-nous-golden-v1"  # noqa: S108 — a recorded path inside fixture bytes, never written to


@pytest.mark.parametrize("backend", ["claudecode", "opencode"])
async def test_golden_files_match_byte_for_byte(
    nous_root: Path, tmp_path: Path, golden_root: Path, backend: str, without_added: Callable[[bytes], bytes]
) -> None:
    out = tmp_path / backend
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), backend, out)
    golden = golden_root / backend
    shared = [path for path in projection.files if (golden / path).is_file() and path not in CHANGED | WALKED]
    mismatched = [
        path
        for path in shared
        if (cut := without_added if path in PERSONA else bytes)((golden / path).read_bytes()).replace(
            f"{GOLDEN_OUT}/{backend}".encode(), b"OUT"
        )
        != cut(projection.files[path]).replace(str(out).encode(), b"OUT")
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
        ("hermes", ".hermes", ["SOUL.md", "workspace/AGENTS.md", "memories/USER.md"]),
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
    nous_root: Path,
    tmp_path: Path,
    golden_root: Path,
    backend: str,
    tree: str,
    files: list[str],
    without_added: Callable[[bytes], bytes],
) -> None:
    live = tmp_path / "live" / tree
    (live / "memory/openhuman").mkdir(parents=True)
    (live / "memory/openhuman/active_user.toml").write_text('user_id = "6abd6edb6e176e3e56822476"\n')
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), backend, tmp_path / backend, live=live)
    assert {path: without_added(projection.files[path]) for path in files} == {
        path: (golden_root / backend / path).read_bytes() for path in files
    }


async def test_golden_hermes_env_follows_the_core(nous_root: Path, tmp_path: Path, nous_tree) -> None:
    """The golden's `.env` is not versioned (the repo ignores `.env`): its two lines are derived from the core instead."""
    projection = await RunService(CheckService()).run(
        GitNous(nous_root, None), "hermes", tmp_path / "hermes", live=tmp_path
    )
    channels, search = nous_tree.config["nomos"]["channels"], nous_tree.config["nomos"]["search"]
    expected = f"DISCORD_ALLOWED_USERS={','.join(channels['discord']['users'])}\nSEARXNG_URL={search['engines']['searxng']['url']}\n"
    assert projection.files[".env"] == expected.encode()
