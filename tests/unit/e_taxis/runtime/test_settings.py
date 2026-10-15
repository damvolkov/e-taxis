"""tests/unit/e_taxis/runtime/settings: the packaged catalog by default, the environment over it."""

from typing import TYPE_CHECKING

from e_taxis.runtime.settings import TaxisSettings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_settings_default_catalog_is_the_packaged_one() -> None:
    assert TaxisSettings().taxis_catalog.parts[-2:] == ("e_taxis", "catalog")


def test_settings_environment_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TAXIS_CATALOG", str(tmp_path))
    monkeypatch.setenv("TAXIS_TIMEOUT", "2.5")
    settings = TaxisSettings()
    assert (settings.taxis_catalog, settings.taxis_timeout) == (tmp_path, 2.5)
