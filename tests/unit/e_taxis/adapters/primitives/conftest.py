"""tests/unit/e_taxis/adapters/primitives: one entry built per test, the run's context in a temp HOME, every adapter
wired to the fake runner and downloader, and the undo that reverts what they record."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.adapters.primitives.binary import BinaryPrimitive
from e_taxis.adapters.primitives.file import FilePrimitive
from e_taxis.adapters.primitives.mcp import McpPrimitive
from e_taxis.adapters.primitives.npm import NpmPrimitive
from e_taxis.adapters.primitives.plugin import PluginPrimitive
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.adapters.primitives.uv import UvPrimitive
from e_taxis.adapters.undo import EffectUndo
from e_taxis.harness.models.catalog import CatalogEntry, Target
from e_taxis.harness.models.primitive import PrimitiveContext

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.harness.models.journal import JournalEffect


@pytest.fixture
def ctx(home: Path, claude_dir: Path) -> PrimitiveContext:
    return PrimitiveContext(target=Target.CLAUDECODE, home=home, claude=claude_dir)


@pytest.fixture
def entry() -> Callable[..., CatalogEntry]:
    """An entry whose one recipe is `primitive` with `with_`; `uninstall` and `owns` as given."""

    def build(
        primitive: str, with_: dict[str, Any], *, uninstall: dict[str, Any] | None = None, owns: tuple[str, ...] = ()
    ) -> CatalogEntry:
        raw = {
            "id": "part",
            "kind": "cli",
            "targets": ["claudecode"],
            "scope": "user",
            "recipes": {"claudecode": {"primitive": primitive, "with": with_}},
            "uninstall": None if uninstall is None else {"primitive": primitive, "with": uninstall},
            "owns": list(owns),
            "probe": "true",
            "verify": "true",
            "status": {"profile": {}, "checked": "2026-10-15", "evidence": "test"},
        }
        return msgspec.convert(raw, CatalogEntry)

    return build


@pytest.fixture
def binary(downloader, runner, tmp_path: Path) -> BinaryPrimitive:
    (tmp_path / "scratch").mkdir()
    return BinaryPrimitive(downloader, runner, temp=tmp_path / "scratch")


@pytest.fixture
def uv(runner) -> UvPrimitive:
    return UvPrimitive(runner)


@pytest.fixture
def npm(runner) -> NpmPrimitive:
    return NpmPrimitive(runner, prefix=None)


@pytest.fixture
def settings() -> SettingsPrimitive:
    return SettingsPrimitive()


@pytest.fixture
def block() -> FilePrimitive:
    return FilePrimitive()


@pytest.fixture
def mcp(runner) -> McpPrimitive:
    return McpPrimitive(runner)


@pytest.fixture
def plugin(runner) -> PluginPrimitive:
    return PluginPrimitive(runner)


@pytest.fixture
def undo(runner, settings: SettingsPrimitive, block: FilePrimitive) -> Callable[..., Any]:
    """Revert effects newest first, as `history undo` does."""
    reverter = EffectUndo(runner, settings, block)

    async def run(*effects: JournalEffect) -> None:
        _ = [await reverter.run(effect) for effect in reversed(effects)]

    return run
