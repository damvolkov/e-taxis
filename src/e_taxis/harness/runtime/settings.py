"""runtime.settings: e-taxis's own knobs — TAXIS_CATALOG, TAXIS_TIMEOUT; for apply TAXIS_NPM_PREFIX,
TAXIS_DOWNLOAD_TIMEOUT, TAXIS_TEMP; and CLAUDE_CONFIG_DIR, Claude Code's own, read so `~/.claude` lands where
Claude reads it. The workflow branch's knobs are `TAXIS_WORKFLOW_*` (runs, steps, the lock, the live OpenCode tree
agents are driven from, what a read-only session may write) and `TAXIS_DISTILL_*` (reverse-distill's second core,
its code graph and caches). `TAXIS_SCHEDULE_UNITS` is where `taxis schedule` writes its units.

The core settings composer only discovers `core/settings/*`, which is materialized and not e-taxis's to
edit: this scope stands alone on the same `BaseSettings` layers, and `Deps` builds it once per run."""

from importlib.resources import files
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr

from e_taxis.infra.config.base import BaseSettings
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
    session's) runs. TAXIS_LOCK is the run lock's token a parent `workflow run` hands its steps. TAXIS_NOUS is the
    e-nous checkout a command reads when `--nous` is not given (the ladder's second rung, `runtime.locator`).

    TAXIS_WORKFLOW_REPORTS: where runs live, relative to the e-nous checkout; _CONCURRENCY bounds the steps in
    flight, _TIMEOUT each step (seconds), _HARNESS_LIMIT a whole run a harness walks (`--harness`), _KWARGS_TIERS the tiers tried in order to read a `query` into kwargs and _KWARGS_LIMIT one such call, _LOCK_WAIT how long a run waits for another; _OPENCODE is the live tree
    agents are driven from (a subagent there is driven from Claude Code's tree, CLAUDE_CONFIG_DIR), _MODEL the model
    OpenCode runs them on (empty: the tree's), _WRITABLE what a read-only session may write.
    TAXIS_DISTILL_BLUEPRINT is the e-arkhetypo checkout read at _REF; _GRAPH the code-graph CLI, _CACHE its
    snapshot cache; _SCOPE the e-nous folders doctrine lives in; _CANDIDATES each miner's cap; _WORKFLOW the
    workflow whose node ports name the miners, the judge and the adversary.

    The planes (`taxis eval`, `taxis enhance`) keep their runs beside the workflows' (TAXIS_WORKFLOW_REPORTS) and
    under the same lock: TAXIS_EVAL_BACKEND is the render they measure, _CONCURRENCY the node runs in flight,
    _CADENCE a run's default, _SCAN_TIMEOUT one SkillSpector scan, _SCAN_FAIL the lowest severity that turns the
    security gate red, _AGENT_TIMEOUT one proposer session, _PROMOTE the heaviest grade each target adopts without a
    human. The heuristic measures (weekly): _TIER the house tier the effect A/B's bare completions run on, _TOKENS
    their answer cap, _RUNNER_TIMEOUT one completion; _SEMANTIC_TIER the tier SkillSpector's LLM stage runs on;
    _PROBE_RUNS the sessions per routing case, _PROBE_CONCURRENCY those in flight, _PROBE_TIMEOUT one session;
    _EFFECT_SEEDS the answers per task and arm, _EFFECT_SPLIT the held-out split the A/B reads.

    TAXIS_SCHEDULE_UNITS is the systemd user units dir `taxis schedule` renders its `taxis-<id>` timers into.
    TAXIS_SOA_STATE is soa-sweep's state, its seen ledger (`ledger.json`) — never config, never the checkout.
    soa-assess (`taxis workflow soa-assess`): TAXIS_ASSESS_WORKFLOW is the workflow whose ports name the agents'
    answers, _TIMEOUT bounds one public-API request (seconds), _LIMIT one fenced process of the bench; TAXIS_SOA_STATE
    is the soa state dir (the `assessed.json` index soa-sweep's fit reads); TAXIS_COMPARE_WORKFLOW the workflow whose ports name soa-compare's agent answers; GH_TOKEN, when set, authenticates the
    GitHub API (unset: 60 requests an hour).

    TAXIS_HUMAN is the mandate a terminal-started `taxis` hands its children (a human command run by a workflow step
    it started); TAXIS_HEADLESS (or e-nous's OPS_GLOBAL__HEADLESS) marks a session an agent drives —
    no human command runs there, mandate or not."""

    taxis_catalog: Path = CATALOG
    taxis_timeout: float = TIMEOUT
    taxis_npm_prefix: Path | None = None
    taxis_download_timeout: float = DOWNLOAD
    taxis_temp: Path | None = None
    claude_config_dir: Path | None = None
    taxis_landrun: Path = LANDRUN
    taxis_lock: str = ""
    taxis_nous: Path | None = None
    taxis_workflow_reports: Path = Path(".reports")
    taxis_workflow_concurrency: int = 4
    taxis_workflow_timeout: float = 1800.0
    taxis_workflow_harness_limit: float = 7200.0
    taxis_workflow_kwargs_tiers: tuple[str, ...] = ("local", "scout")
    taxis_workflow_kwargs_limit: float = 60.0
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
    taxis_assess_workflow: str = "soa-assess"
    taxis_assess_timeout: float = 20.0
    taxis_assess_limit: float = 900.0
    taxis_soa_state: Path = Path("~/.local/state/e-taxis/soa")
    taxis_compare_workflow: str = "soa-compare"
    gh_token: SecretStr | None = None
    taxis_eval_backend: str = "opencode"
    taxis_eval_concurrency: int = 4
    taxis_eval_cadence: Cadence = Cadence.MANUAL
    taxis_eval_scan_timeout: float = 300.0
    taxis_eval_scan_fail: str = "HIGH"
    taxis_eval_agent_timeout: float = 900.0
    taxis_eval_promote: dict[str, str] = PROMOTE
    taxis_eval_tier: str = "scout"
    taxis_eval_semantic_tier: str = "builder"
    taxis_eval_tokens: int = 8192
    taxis_eval_runner_timeout: float = 300.0
    taxis_eval_probe_runs: int = 3
    taxis_eval_probe_concurrency: int = 6
    taxis_eval_probe_timeout: float = 180.0
    taxis_eval_effect_seeds: int = 5
    taxis_eval_effect_split: str = "test"
    taxis_schedule_units: Path = Path("~/.config/systemd/user")
    taxis_human: bool = False
    taxis_headless: bool = Field(default=False, validation_alias=AliasChoices("TAXIS_HEADLESS", "OPS_GLOBAL__HEADLESS"))
