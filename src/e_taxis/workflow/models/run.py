"""models.run: one run of a workflow — its manifest, every step run it recorded, and where it all lives.

The ledger is a stream of `NodeRun`, append-only; the report is derived from it, so it can be rebuilt from the
ledger alone.

    <nous>/.reports/workflows/<id>/<run>/
      run.json        RunManifest: the workflow, its bound parameters, the e-nous commit, the graph
      ledger.jsonl    one NodeRun per line — the truth
      nodes/<step>/out.md   what each step said (an agent step's answer is read back from here)
      report.md       the run, step by step"""

import datetime as dt
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path

from msgspec import Struct

from e_taxis.workflow.models.graph import GraphSpec
from e_taxis.workflow.models.metrics import Metrics

##### DEFAULTS #####
OUT: str = "out.md"


##### TYPES #####
class Status(StrEnum):
    """How a step run ended: `idle` was not due and blocks nothing; `skip` could not run (upstream not green, or
    nothing to do); `fail` ran and said no; `error` broke."""

    OK = auto()
    FAIL = auto()
    IDLE = auto()
    SKIP = auto()
    ERROR = auto()

    @property
    def green(self) -> bool:
        """Whether a downstream step may run over this."""
        return self in {Status.OK, Status.IDLE}

    @property
    def broken(self) -> bool:
        """Whether this makes the run fail."""
        return self in {Status.FAIL, Status.ERROR}


class Reply(Struct, frozen=True):
    """One answer from a command or an agent: its text, fresh tokens and cache reads apart."""

    text: str
    tokens: int = 0
    cached: int = 0


class Outcome(Struct, frozen=True, kw_only=True):
    """What a step returns; the executor stamps it into a `NodeRun`."""

    status: Status
    metrics: Metrics | None = None
    reason: str = ""
    tokens: int = 0
    cached: int = 0
    runner: str = ""
    artifacts: tuple[str, ...] = ()


class NodeRun(Struct, frozen=True, kw_only=True):
    """One step, as it happened."""

    run_id: str
    node: str
    status: Status
    started: dt.datetime
    ended: dt.datetime
    input_hash: str
    output_hash: str
    metrics: Metrics | None = None
    reason: str = ""
    tokens: int = 0
    cached: int = 0
    runner: str = ""
    artifacts: tuple[str, ...] = ()

    @property
    def seconds(self) -> float:
        return (self.ended - self.started).total_seconds()


class RunManifest(Struct, frozen=True, kw_only=True):
    """What a run was asked to do and the exact world it did it in: the e-nous checkout, its commit, the graph."""

    run_id: str
    workflow: str
    nous: str
    base_sha: str
    started: dt.datetime
    graph: GraphSpec
    params: dict[str, str] = {}


@dataclass(frozen=True, slots=True)
class RunPaths:
    """Every place a run writes, all of it under its folder."""

    root: Path

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.jsonl"

    @property
    def manifest(self) -> Path:
        return self.root / "run.json"

    @property
    def report(self) -> Path:
        return self.root / "report.md"

    def node(self, step: str) -> Path:
        """A step's own folder: its scratch and its `out.md`."""
        return self.root / "nodes" / step

    def out(self, step: str) -> Path:
        return self.node(step) / OUT


class RunReport(Struct, frozen=True, kw_only=True):
    """A run, concluded: its manifest and every step run, rebuilt from the ledger alone; `markdown` for a human."""

    manifest: RunManifest
    runs: tuple[NodeRun, ...]
    folder: str

    @property
    def broken(self) -> tuple[NodeRun, ...]:
        """The steps that make the run fail."""
        return tuple(run for run in self.runs if run.status.broken)

    @property
    def totals(self) -> str:
        counted = Counter(run.status.value for run in self.runs)
        tokens = sum(run.tokens for run in self.runs)
        cached = sum(run.cached for run in self.runs)
        statuses = " · ".join(f"{status} {count}" for status, count in sorted(counted.items()))
        return f"{statuses} · {tokens} tokens" + (f" (+{cached} cached)" if cached else "")

    @property
    def markdown(self) -> str:
        manifest = self.manifest
        params = " · ".join(f"`{name}={value}`" for name, value in manifest.params.items() if value) or "none"
        rows = "\n".join(
            f"| {run.node} | {run.status} | {run.runner or '—'} | {run.seconds:.1f} | {run.tokens} | "
            f"{' '.join(run.reason.split()).replace('|', '/')} |"
            for run in self.runs
        )
        return (
            f"# workflow {manifest.workflow} · {manifest.run_id}\n\n"
            f"e-nous `{manifest.nous}` @ `{manifest.base_sha[:7] or 'worktree'}` · parameters: {params}\n\n"
            "| Step | Status | Runner | Seconds | Tokens | Reason |\n|---|---|---|---:|---:|---|\n"
            f"{rows}\n\n**{self.totals}**\n"
        )
