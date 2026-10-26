"""tests/unit/e_taxis/transpile/services/run: a checked core projected per backend, written to a scratch tree."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.error import CheckError, RenderError
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.parametrize("backend", ["claudecode", "opencode"])
async def test_run_writes_the_projection(nous_root: Path, tmp_path: Path, backend: str) -> None:
    out = tmp_path / "out"
    projection = await RunService(CheckService()).run(GitNous(nous_root, None), backend, out)
    assert all((out / path).read_bytes() == data for path, data in projection.files.items())
    assert ("CLAUDE.md" if backend == "claudecode" else "AGENTS.md") in projection.files


async def test_run_refuses_a_checkout_its_law_refuses(
    nous_root: Path, tmp_path: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit("specs/tekton/claudecode.yaml", lambda s: s["map"]["config"]["rows"][1].update({"from": "main.ghost"}))
    with pytest.raises(CheckError):
        await RunService(CheckService()).run(GitNous(nous_root, None), "claudecode", tmp_path / "out")


async def test_run_refuses_an_unknown_backend(nous_root: Path, tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="no spec"):
        await RunService(CheckService()).run(GitNous(nous_root, None), "ghost", tmp_path / "out")


async def test_run_bindings_read_the_harness(nous_root: Path, tmp_path: Path) -> None:
    live = tmp_path / "live"
    (live / "memory/openhuman").mkdir(parents=True)
    (live / "memory/openhuman/active_user.toml").write_text('user_id = "u1"\n')
    projection = await RunService(CheckService()).run(
        GitNous(nous_root, None), "openhuman", tmp_path / "out", live=live
    )
    assert "memory/openhuman/users/u1/config.toml" in projection.files
    assert projection.links["memory/openhuman/users/u1/workspace/SOUL.md"] == "memory/persona/SOUL.md"
    json_spec = {"bindings": {"who": {"read": "w.json#name"}}}
    (live / "w.json").write_text('{"name": "n"}')
    assert await RunService.bindings(json_spec, live) == {"who": "n"}


async def test_run_binding_without_its_file_refuses(nous_root: Path, tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="binding `profile`"):
        await RunService(CheckService()).run(
            GitNous(nous_root, None), "openhuman", tmp_path / "out", live=tmp_path / "nothing"
        )
