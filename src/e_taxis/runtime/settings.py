"""runtime.settings: e-taxis's own knobs — TAXIS_CATALOG, TAXIS_TIMEOUT.

The core settings composer only discovers `core/settings/*`, which is materialized and not e-taxis's to
edit: this scope stands alone on the same `BaseSettings` layers, and `Deps` builds it once per run."""

from importlib.resources import files
from pathlib import Path

from core.settings.base import BaseSettings

##### DEFAULTS #####
### the catalog ships inside the package: `files` finds it in a checkout and in an installed wheel alike.
CATALOG: Path = Path(str(files("e_taxis") / "catalog"))
TIMEOUT: float = 10.0


class TaxisSettings(BaseSettings):
    """TAXIS_CATALOG points at another catalog root (`entries/`, `profiles/`); TAXIS_TIMEOUT bounds each probe."""

    taxis_catalog: Path = CATALOG
    taxis_timeout: float = TIMEOUT
