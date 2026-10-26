"""runtime.settings: e-taxis's own knobs — TAXIS_CATALOG, TAXIS_TIMEOUT; for apply TAXIS_NPM_PREFIX,
TAXIS_DOWNLOAD_TIMEOUT, TAXIS_TEMP; and CLAUDE_CONFIG_DIR, Claude Code's own, read so `~/.claude` lands where
Claude reads it. The workflow branch's knobs are `TAXIS_WORKFLOW_*` (runs, steps, the lock, the live OpenCode tree
agents are driven from, what a read-only session may write) and `TAXIS_DISTILL_*` (reverse-distill's second core,
its code graph and caches).

The core settings composer only discovers `core/settings/*`, which is materialized and not e-taxis's to
edit: this scope stands alone on the same `BaseSettings` layers, and `Deps` builds it once per run."""

from importlib.resources import files
from pathlib import Path

from e_taxis.core.settings.base import BaseSettings

##### DEFAULTS #####
### the catalog ships inside the harness branch: `files` finds it in a checkout and in an installed wheel alike.
CATALOG: Path = Path(str(files("e_taxis.harness") / "catalog"))
TIMEOUT: float = 10.0
DOWNLOAD: float = 300.0
### the Landlock CLI a trial fences its phantoms with: pinned and checksum-verified where it is installed.
LANDRUN: Path = Path("~/.local/bin/landrun")
### where a read-only agent session may write: OpenCode's own cache, data and state — never a repo, never a config.
WRITABLE: tuple[Path, ...] = (Path("~/.cache"), Path("~/.local/share"), Path("~/.local/state"))


class TaxisSettings(BaseSettings):
    """TAXIS_CATALOG points at another catalog root (`entries/`, `profiles/`); TAXIS_TIMEOUT bounds each probe.

    TAXIS_NPM_PREFIX: where `npm -g` installs (unset: the user's npm prefix). TAXIS_DOWNLOAD_TIMEOUT bounds a
    whole binary download. TAXIS_TEMP stages downloads (unset: the system's temp dir). CLAUDE_CONFIG_DIR, when
    set, is where `~/.claude` resolves. TAXIS_LANDRUN is the landrun binary a trial's fence (and a read-only agent
    session's) runs. TAXIS_LOCK is the run lock's token a parent `workflow run` hands its steps.

    TAXIS_WORKFLOW_REPORTS: where runs live, relative to the e-nous checkout; _CONCURRENCY bounds the steps in
    flight, _TIMEOUT each step (seconds), _LOCK_WAIT how long a run waits for another; _OPENCODE is the live tree
    agents are driven from, _MODEL the model they run on (empty: the tree's), _WRITABLE what a read-only session may
    write. TAXIS_DISTILL_BLUEPRINT is the e-arkhetypo checkout read at _REF; _GRAPH the code-graph CLI, _CACHE its
    snapshot cache; _SCOPE the e-nous folders doctrine lives in; _CANDIDATES each miner's cap; _WORKFLOW the
    workflow whose node ports name the miners, the judge and the adversary."""

    taxis_catalog: Path = CATALOG
    taxis_timeout: float = TIMEOUT
    taxis_npm_prefix: Path | None = None
    taxis_download_timeout: float = DOWNLOAD
    taxis_temp: Path | None = None
    claude_config_dir: Path | None = None
    taxis_landrun: Path = LANDRUN
    taxis_lock: str = ""
    taxis_workflow_reports: Path = Path(".reports")
    taxis_workflow_concurrency: int = 4
    taxis_workflow_timeout: float = 1800.0
    taxis_workflow_lock_wait: float = 600.0
    taxis_workflow_opencode: Path = Path("~/.config/opencode")
    taxis_workflow_model: str = ""
    taxis_workflow_writable: tuple[Path, ...] = WRITABLE
    taxis_distill_workflow: str = "reverse-distill"
    taxis_distill_blueprint: Path = Path("~/workspaces/damien/e-arkhetypo")
    taxis_distill_ref: str = "origin/main"
    taxis_distill_graph: str = "codebase-memory-mcp"
    taxis_distill_cache: Path = Path("~/.cache/reverse-distill")
    taxis_distill_scope: tuple[str, ...] = ("core", "specs/tekton")
    taxis_distill_candidates: int = 12
