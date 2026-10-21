"""tests/unit/e_taxis/services: the use cases over the real file catalog and real, harmless shell probes; the writing
services over the real primitives, wired to the fake runner and downloader, writing into the temp HOME."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.primitives.binary import BinaryPrimitive
from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.adapters.primitives.file import FilePrimitive
from e_taxis.adapters.primitives.mcp import McpPrimitive
from e_taxis.adapters.primitives.npm import NpmPrimitive
from e_taxis.adapters.primitives.plugin import PluginPrimitive
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.adapters.primitives.uv import UvPrimitive
from e_taxis.adapters.probe import ShellProbe
from e_taxis.adapters.source import NousSource, ProfileSource
from e_taxis.harness.models.catalog import Primitive
from e_taxis.harness.services.apply import ApplyService
from e_taxis.harness.services.doctor import DoctorService
from e_taxis.harness.services.plan import PlanService
from e_taxis.harness.services.resolver import ResolverService
from e_taxis.harness.services.uninstall import UninstallService
from e_taxis.harness.services.verify import VerifyService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.harness.models.catalog import Target
    from e_taxis.harness.models.journal import JournalEffect
    from e_taxis.harness.models.ports import PrimitivePort
    from e_taxis.harness.models.wanted import WantedPart


class ListSource:
    """SourcePort over a fixed tuple: the wanted parts a test names, whatever the target."""

    def __init__(self, *parts: WantedPart) -> None:
        self.parts = parts

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]:
        return self.parts


@pytest.fixture
def resolver(catalog_root: Path) -> ResolverService:
    return ResolverService(FileCatalog(catalog_root))


@pytest.fixture
def probe() -> ShellProbe:
    return ShellProbe(timeout=5)


@pytest.fixture
def planner(resolver: ResolverService, probe: ShellProbe) -> PlanService:
    return PlanService(resolver, probe)


@pytest.fixture
def verifier(resolver: ResolverService, probe: ShellProbe) -> VerifyService:
    return VerifyService(resolver, probe)


@pytest.fixture
def house(catalog_root: Path) -> ProfileSource:
    return ProfileSource(catalog_root, "house")


@pytest.fixture
def nous(nous_root: Path) -> NousSource:
    return NousSource(nous_root)


@pytest.fixture
def listed() -> type[ListSource]:
    return ListSource


@pytest.fixture
def doctor(doctor_root: Path) -> DoctorService:
    return DoctorService(FileCatalog(doctor_root))


class ListRecorder:
    """RecorderPort over a list: what the service asked the journal to keep."""

    def __init__(self) -> None:
        self.effects: list[JournalEffect] = []

    def record(self, *effects: JournalEffect) -> None:
        self.effects.extend(effects)


@pytest.fixture
def recorder() -> ListRecorder:
    return ListRecorder()


@pytest.fixture
def environ() -> dict[str, str]:
    return {}


@pytest.fixture
def primitives(runner, downloader, tmp_path: Path) -> dict[Primitive, PrimitivePort]:
    """The real adapters, on the fake runner and downloader: what they write lands in the temp HOME."""
    settings = SettingsPrimitive()
    return {
        Primitive.BINARY: BinaryPrimitive(downloader, runner, temp=None),
        Primitive.UV_TOOL: UvPrimitive(runner),
        Primitive.NPM: NpmPrimitive(runner, prefix=None),
        Primitive.SETTINGS: settings,
        Primitive.ENV: settings,
        Primitive.FILE: FilePrimitive(),
        Primitive.CLAUDE_MCP: McpPrimitive(runner),
        Primitive.CLAUDE_PLUGIN: PluginPrimitive(runner),
        Primitive.COMPOSE: ComposePrimitive(),
    }


@pytest.fixture
def realm(world_root: Path) -> ResolverService:
    return ResolverService(FileCatalog(world_root))


@pytest.fixture
def applier(
    realm: ResolverService,
    probe: ShellProbe,
    primitives: dict[Primitive, PrimitivePort],
    recorder: ListRecorder,
    home: Path,
    claude_dir: Path,
    environ: dict[str, str],
) -> ApplyService:
    return ApplyService(
        realm, PlanService(realm, probe), probe, primitives, recorder, home=home, claude=claude_dir, environ=environ
    )


@pytest.fixture
def uninstaller(
    realm: ResolverService,
    probe: ShellProbe,
    primitives: dict[Primitive, PrimitivePort],
    recorder: ListRecorder,
    home: Path,
    claude_dir: Path,
) -> UninstallService:
    return UninstallService(realm, probe, primitives, recorder, home=home, claude=claude_dir)


@pytest.fixture
def profile(world_root: Path) -> Callable[[str], ProfileSource]:
    return lambda name: ProfileSource(world_root, name)
