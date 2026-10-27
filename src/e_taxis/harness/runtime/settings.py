"""runtime.settings: e-taxis's own knobs — TAXIS_CATALOG, TAXIS_TIMEOUT; for apply TAXIS_NPM_PREFIX,
TAXIS_DOWNLOAD_TIMEOUT, TAXIS_TEMP; and CLAUDE_CONFIG_DIR, Claude Code's own, read so `~/.claude` lands where
Claude reads it. The workflow branch's knobs are `TAXIS_WORKFLOW_*` (runs, steps, the lock, the live OpenCode tree
agents are driven from, what a read-only session may write) and `TAXIS_DISTILL_*` (reverse-distill's second core,
its code graph and caches).

The core settings composer only discovers `core/settings/*`, which is materialized and not e-taxis's to
edit: this scope stands alone on the same `BaseSettings` layers, and `Deps` builds it once per run."""

from importlib.resources import files
from pathlib import Path

from pydantic import AliasChoices, Field

from e_taxis.core.settings.base import BaseSettings
from e_taxis.workflow.models.plane import Cadence

##### DEFAULTS #####
### the catalog ships inside the harness branch: `files` finds it in a checkout and in an installed wheel alike.
CATALOG: Path = Path(str(files("e_taxis.harness") / "catalog"))
TIMEOUT: float = 10.0
DOWNLOAD: float = 300.0
### the Landlock CLI a trial fences its phantoms with: pinned and checksum-verified where it is installed.
LANDRUN: Path = Path("~/.local/bin/landrun")
### where a read-only agent session may write: the drivers' (OpenCode's, Claude Code's) own cache, data and state —
### never a repo, never a config.
WRITABLE: tuple[Path, ...] = (Path("~/.cache"), Path("~/.local/share"), Path("~/.local/state"))
### the heaviest grade an enhancement adopts without a human, per target (e-nous ops `promote:`); `none` adopts nothing.
PROMOTE: dict[str, str] = {
    "skill": "none",
    "agent": "cosmetic",
    "command": "cosmetic",
    "workflow": "none",
    "tool": "none",
    "persona": "none",
    "config": "none",
    "spec": "deepening",
}


class TaxisSettings(BaseSettings):
    """TAXIS_CATALOG points at another catalog root (`entries/`, `profiles/`); TAXIS_TIMEOUT bounds each probe.

    TAXIS_NPM_PREFIX: where `npm -g` installs (unset: the user's npm prefix). TAXIS_DOWNLOAD_TIMEOUT bounds a
    whole binary download. TAXIS_TEMP stages downloads (unset: the system's temp dir). CLAUDE_CONFIG_DIR, when
    set, is where `~/.claude` resolves. TAXIS_LANDRUN is the landrun binary a trial's fence (and a read-only agent
    session's) runs. TAXIS_LOCK is the run lock's token a parent `workflow run` hands its steps.

    TAXIS_WORKFLOW_REPORTS: where runs live, relative to the e-nous checkout; _CONCURRENCY bounds the steps in
    flight, _TIMEOUT each step (seconds), _LOCK_WAIT how long a run waits for another; _OPENCODE is the live tree
    agents are driven from (a subagent there is driven from Claude Code's tree, CLAUDE_CONFIG_DIR), _MODEL the model
    OpenCode runs them on (empty: the tree's), _WRITABLE what a read-only session may write.
    TAXIS_DISTILL_BLUEPRINT is the e-arkhetypo checkout read at _REF; _GRAPH the code-graph CLI, _CACHE its
    snapshot cache; _SCOPE the e-nous folders doctrine lives in; _CANDIDATES each miner's cap; _WORKFLOW the
    workflow whose node ports name the miners, the judge and the adversary.

    The planes (`taxis eval`, `taxis enhance`) keep their runs beside the workflows' (TAXIS_WORKFLOW_REPORTS) and
    under the same lock: TAXIS_EVAL_BACKEND is the render they measure, _CONCURRENCY the node runs in flight,
    _CADENCE a run's default, _SCAN_TIMEOUT one SkillSpector scan, _SCAN_FAIL the lowest severity that turns the
    security gate red, _AGENT_TIMEOUT one proposer session, _PROMOTE the heaviest grade each target adopts without a
    human. TAXIS_HUMAN is the mandate a terminal-started `taxis` hands its children (a human command run by a
    workflow step it started); TAXIS_HEADLESS (or e-nous's OPS_GLOBAL__HEADLESS) marks a session an agent drives —
    no human command runs there, mandate or not."""

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
    taxis_eval_backend: str = "opencode"
    taxis_eval_concurrency: int = 4
    taxis_eval_cadence: Cadence = Cadence.MANUAL
    taxis_eval_scan_timeout: float = 300.0
    taxis_eval_scan_fail: str = "HIGH"
    taxis_eval_agent_timeout: float = 900.0
    taxis_eval_promote: dict[str, str] = PROMOTE
    taxis_human: bool = False
    taxis_headless: bool = Field(default=False, validation_alias=AliasChoices("TAXIS_HEADLESS", "OPS_GLOBAL__HEADLESS"))
