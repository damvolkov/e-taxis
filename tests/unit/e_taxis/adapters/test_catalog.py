"""tests/unit/e_taxis/adapters/catalog: one YAML file per entry — parsed ones kept, broken ones named with the reason."""

from typing import TYPE_CHECKING

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.harness.models.ports import CatalogPort

if TYPE_CHECKING:
    from pathlib import Path


def test_catalog_satisfies_the_port(catalog_root: Path) -> None:
    assert isinstance(FileCatalog(catalog_root), CatalogPort)


async def test_catalog_load_reads_every_entry_in_file_order(catalog_root: Path) -> None:
    catalog = await FileCatalog(catalog_root).load()
    assert [entry.id for entry in catalog.entries] == ["alpha", "beta", "delta", "epsilon", "gamma"]
    assert catalog.broken == ()


async def test_catalog_load_names_each_broken_file(doctor_root: Path) -> None:
    catalog = await FileCatalog(doctor_root).load()
    assert dict(catalog.broken).keys() == {"broken.yaml", "stray.yaml"}
    assert "colour" in dict(catalog.broken)["stray.yaml"]
    assert len(catalog.entries) == 3


async def test_catalog_load_without_entries_is_empty(tmp_path: Path) -> None:
    assert await FileCatalog(tmp_path).load() == await FileCatalog(tmp_path / "absent").load()
