"""tests/unit/e_taxis/runtime/settings: the packaged catalog by default, the environment over it."""

from typing import TYPE_CHECKING

from e_taxis.harness.runtime.settings import TaxisSettings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_settings_default_catalog_is_the_packaged_one() -> None:
    assert TaxisSettings().taxis_catalog.parts[-2:] == ("harness", "catalog")


def test_settings_environment_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TAXIS_CATALOG", str(tmp_path))
    monkeypatch.setenv("TAXIS_TIMEOUT", "2.5")
    settings = TaxisSettings()
    assert (settings.taxis_catalog, settings.taxis_timeout) == (tmp_path, 2.5)


def test_settings_writing_knobs_default_to_the_user_s_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    settings = TaxisSettings()
    assert (settings.taxis_npm_prefix, settings.taxis_temp, settings.claude_config_dir) == (None, None, None)
    assert settings.taxis_download_timeout == 300.0


def test_settings_writing_knobs_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TAXIS_NPM_PREFIX", str(tmp_path / "npm"))
    monkeypatch.setenv("TAXIS_TEMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("TAXIS_DOWNLOAD_TIMEOUT", "30")
    settings = TaxisSettings()
    assert (settings.taxis_npm_prefix, settings.taxis_temp, settings.taxis_download_timeout) == (
        tmp_path / "npm",
        tmp_path / "tmp",
        30.0,
    )
    assert settings.claude_config_dir == tmp_path / "claude"


def test_settings_nous_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert TaxisSettings().taxis_nous is None
    monkeypatch.setenv("TAXIS_NOUS", str(tmp_path))
    assert TaxisSettings().taxis_nous == tmp_path
