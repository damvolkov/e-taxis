"""tests/e2e/land: a real landing in a sandboxed HOME — real files, Claude's real MCP registry, the real undo.

The landing must leave nothing to do (a second plan is empty), and undoing every
recorded effect, newest first, must leave the sandbox as it was: no file, no registration."""

from typing import TYPE_CHECKING, Any, ClassVar

import msgspec
import pytest

from e_taxis.adapters.primitives.file import FilePrimitive
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.adapters.undo import EffectUndo
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import LandService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


class DictStore:
    name: ClassVar[str] = "dict"

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def set(self, key: str, value: bytes) -> None:
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def keys(self, prefix: str = ""):
        for key in sorted(self.data):
            if key.startswith(prefix):
                yield key


class ListRecorder:
    def __init__(self) -> None:
        self.effects: list[Any] = []

    def record(self, *effects: Any) -> None:
        self.effects.extend(effects)


async def test_land_claudecode_settles_and_undoes(nous_root: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    recorder = ListRecorder()
    lander = LandService(RunService(CheckService()), ProcessRunner(), DictStore(), recorder)
    source = GitNous(nous_root, None)
    landed = await lander.apply(source, "claudecode", home)
    registered = msgspec.json.decode((home / ".claude.json").read_bytes())["mcpServers"]
    assert {finding.path.split("#")[1] for finding in landed.findings if finding.path.startswith("mcp-user#")} == set(
        registered
    )
    again = await lander.plan(source, "claudecode", home)
    assert again.findings == ()
    undo = EffectUndo(ProcessRunner(), SettingsPrimitive(), FilePrimitive())
    _ = [await undo.run(effect) for effect in reversed(recorder.effects)]
    ### Claude's CLI keeps its own backups of ~/.claude.json under backups/: the harness's state, never ours.
    assert [path for path in (home / ".claude").rglob("*") if path.is_file() and "backups" not in path.parts] == []
    assert msgspec.json.decode((home / ".claude.json").read_bytes()).get("mcpServers", {}) == {}
