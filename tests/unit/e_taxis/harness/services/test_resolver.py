"""tests/unit/e_taxis/services/resolver: wanted ⨝ catalog — target filter, requires pulled in, DAG order, unknowns."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import CatalogCycleError, CatalogError
from e_taxis.harness.models.wanted import WantedPart
from e_taxis.harness.services.resolver import ResolverService

if TYPE_CHECKING:
    from pathlib import Path


async def test_resolver_resolve_orders_by_requires_and_reports_unknown(resolver: ResolverService, house) -> None:
    resolution = await resolver.resolve(house, Target.CLAUDECODE)
    assert [(item.entry.id, item.order) for item in resolution.resolved] == [("alpha", 0), ("delta", 1), ("beta", 2)]
    assert [part.id for part in resolution.unknown] == ["ghost"]


async def test_resolver_resolve_drops_parts_for_another_target(resolver: ResolverService, house) -> None:
    resolution = await resolver.resolve(house, Target.OPENCODE)
    assert [item.entry.id for item in resolution.resolved] == ["alpha", "gamma"]


async def test_resolver_resolve_pulls_in_what_a_part_requires(resolver: ResolverService, listed) -> None:
    resolution = await resolver.resolve(listed(WantedPart(id="beta", source="test")), Target.CLAUDECODE)
    assert [(item.entry.id, item.wanted.source) for item in resolution.resolved] == [
        ("alpha", "requires:beta"),
        ("beta", "test"),
    ]


async def test_resolver_resolve_reports_a_dangling_require_as_unknown(dangling_root: Path, listed) -> None:
    resolution = await ResolverService(FileCatalog(dangling_root)).resolve(
        listed(WantedPart(id="lone", source="test")), Target.CLAUDECODE
    )
    assert [item.entry.id for item in resolution.resolved] == ["lone"]
    assert [(part.id, part.source) for part in resolution.unknown] == [("nowhere", "requires:lone")]


async def test_resolver_resolve_refuses_a_cycle(cycle_root: Path, listed) -> None:
    with pytest.raises(CatalogCycleError, match="requires cycle"):
        await ResolverService(FileCatalog(cycle_root)).resolve(listed(), Target.CLAUDECODE)


async def test_resolver_resolve_refuses_a_broken_catalog(doctor_root: Path, listed) -> None:
    with pytest.raises(CatalogError, match=r"broken\.yaml.*taxis doctor"):
        await ResolverService(FileCatalog(doctor_root)).resolve(listed(), Target.CLAUDECODE)


@pytest.mark.parametrize(
    ("target", "expected"),
    [(None, ["alpha", "beta", "delta", "epsilon", "gamma"]), (Target.OPENCODE, ["alpha", "epsilon", "gamma"])],
    ids=["all", "opencode"],
)
async def test_resolver_listing(resolver: ResolverService, target: Target | None, expected: list[str]) -> None:
    assert [entry.id for entry in await resolver.listing(target)] == expected
