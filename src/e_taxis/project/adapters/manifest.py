"""adapters.manifest: the registry file as a port — e-serde decodes it straight into the validated DTOs."""

from typing import TYPE_CHECKING

import eserde

from e_taxis.project.models.manifest import Manifest

if TYPE_CHECKING:
    from pathlib import Path


class ManifestReader:
    """Reads and validates ``data/templates.yml``; every template is checked at load, not at use."""

    __slots__ = ("path",)

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Manifest:
        try:
            return eserde.load(self.path, type=Manifest)
        except eserde.LoaderError as exc:
            msg = f"invalid template registry {self.path}: {exc}"
            raise ValueError(msg) from exc
