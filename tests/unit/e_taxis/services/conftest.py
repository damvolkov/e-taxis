"""tests/unit/e_taxis/services: the use cases over the real file catalog and real, harmless shell probes."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.probe import ShellProbe
from e_taxis.adapters.source import EngineerSource, ProfileSource
from e_taxis.services.doctor import DoctorService
from e_taxis.services.plan import PlanService
from e_taxis.services.resolver import ResolverService
from e_taxis.services.verify import VerifyService

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.models.catalog import Target
    from e_taxis.models.wanted import WantedPart


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
def engineer(engineer_root: Path) -> EngineerSource:
    return EngineerSource(engineer_root)


@pytest.fixture
def listed() -> type[ListSource]:
    return ListSource


@pytest.fixture
def doctor(doctor_root: Path) -> DoctorService:
    return DoctorService(FileCatalog(doctor_root))
