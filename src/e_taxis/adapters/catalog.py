"""adapters.catalog: the catalog on disk — `entries/*.yaml`, one entry per file, decoded straight into the schema."""

from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.models.catalog import Catalog, CatalogEntry

if TYPE_CHECKING:
    from pathlib import Path


##### TYPES #####
class FileCatalog:
    """Satisfies CatalogPort over a directory holding `entries/`; an absent directory is an empty catalog."""

    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _load_file(path: anyio.Path) -> CatalogEntry | tuple[str, str]:
        """The entry, or `(file, reason)`: msgspec's DecodeError covers YAML syntax and schema alike."""
        try:
            return msgspec.yaml.decode(await path.read_bytes(), type=CatalogEntry)
        except msgspec.DecodeError as exc:
            return (path.name, str(exc))

    ############################################################

    ##### PUBLIC #####

    async def load(self) -> Catalog:
        files = sorted([path async for path in anyio.Path(self._root / "entries").glob("*.yaml")])
        loaded = [await self._load_file(path) for path in files]
        return Catalog(
            entries=tuple(item for item in loaded if isinstance(item, CatalogEntry)),
            broken=tuple(item for item in loaded if isinstance(item, tuple)),
        )
