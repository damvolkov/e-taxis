"""runtime.settings: e-taxis's own knobs — TAXIS_CATALOG, TAXIS_TIMEOUT; for apply TAXIS_NPM_PREFIX,
TAXIS_DOWNLOAD_TIMEOUT, TAXIS_TEMP; and CLAUDE_CONFIG_DIR, Claude Code's own, read so `~/.claude` lands where
Claude reads it.

The core settings composer only discovers `core/settings/*`, which is materialized and not e-taxis's to
edit: this scope stands alone on the same `BaseSettings` layers, and `Deps` builds it once per run."""

from importlib.resources import files
from pathlib import Path

from core.settings.base import BaseSettings

##### DEFAULTS #####
### the catalog ships inside the package: `files` finds it in a checkout and in an installed wheel alike.
CATALOG: Path = Path(str(files("e_taxis") / "catalog"))
TIMEOUT: float = 10.0
DOWNLOAD: float = 300.0


class TaxisSettings(BaseSettings):
    """TAXIS_CATALOG points at another catalog root (`entries/`, `profiles/`); TAXIS_TIMEOUT bounds each probe.

    TAXIS_NPM_PREFIX: where `npm -g` installs (unset: the user's npm prefix). TAXIS_DOWNLOAD_TIMEOUT bounds a
    whole binary download. TAXIS_TEMP stages downloads (unset: the system's temp dir). CLAUDE_CONFIG_DIR, when
    set, is where `~/.claude` resolves."""

    taxis_catalog: Path = CATALOG
    taxis_timeout: float = TIMEOUT
    taxis_npm_prefix: Path | None = None
    taxis_download_timeout: float = DOWNLOAD
    taxis_temp: Path | None = None
    claude_config_dir: Path | None = None
