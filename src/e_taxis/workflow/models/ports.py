"""models.ports: what the workflow engine asks of the world — run a command, drive an agent, keep a ledger, run a step;
and for the planes, a git sandbox, a scanner, the evaluator's ledgers, and a node over one subject.

The context is part of the contract: a run's resources (manifest, paths, ledger) are fixed when it starts; the
evidence lives only in the ledger, append-only and typed. A step reads upstream evidence through its context."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from e_taxis.transpile.models.ports import CapturePort, NousPort
from e_taxis.transpile.models.trial import TrialReport
from e_taxis.workflow.models.case import QuerySet, TaskSet
from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.plane import NodeCard, NodeSpec, PlaneManifest, PlanePaths
from e_taxis.workflow.models.run import NodeRun, Outcome, Reply, RunManifest, RunPaths
from e_taxis.workflow.models.security import ScanResult


##### PORTS #####
@runtime_checkable
class CommandPort(Protocol):
    """Run one argv, no shell of its own, within `limit` seconds: stdout on exit 0, a CommandError otherwise; `env`
    overrides the inherited environment."""

    async def run(
        self,
        *argv: str,
        limit: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        echo: str = "",
    ) -> str: ...


@runtime_checkable
class AgentPort(Protocol):
    """One headless session of a house agent in `cwd`; `readonly` must hold, not merely be asked for."""

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply: ...


@runtime_checkable
class CanaryPort(Protocol):
    """Whether a fence holds: a write inside it lands, a write outside it is refused."""

    async def canary(self, inside: Path, outside: Path) -> bool: ...


@runtime_checkable
class LedgerPort(Protocol):
    """The run's append-only memory: durable first, visible second."""

    async def append(self, run: NodeRun) -> None: ...

    def latest(self, node: str, subject: str = "") -> NodeRun | None: ...

    def runs(self) -> tuple[NodeRun, ...]: ...


@runtime_checkable
class LockPort(Protocol):
    """One run at a time per checkout: hold `path` for the block, yielding the token a nested run re-enters with."""

    def hold(self, path: Path, command: str) -> AbstractAsyncContextManager[str]: ...


##### CONTEXT #####
@dataclass(frozen=True, slots=True)
class RunState:
    """The resources of one run. Immutable; the ledger is the only thing that grows."""

    manifest: RunManifest
    paths: RunPaths
    ledger: LedgerPort


@dataclass(frozen=True, slots=True)
class NodeContext:
    """What one step run sees: the run and its own spec."""

    state: RunState
    spec: StepSpec

    @property
    def workdir(self) -> Path:
        return self.state.paths.node(self.spec.id)

    def upstream(self, node: str) -> NodeRun | None:
        return self.state.ledger.latest(node)


@runtime_checkable
class NodePort(Protocol):
    """A step: one async call from its context to an outcome. Never raises for a verdict."""

    async def run(self, context: NodeContext) -> Outcome: ...


##### PLANE PORTS #####
@runtime_checkable
class SandboxPort(Protocol):
    """git over a checkout and the run's clone of it: every repo is named per call, so one adapter serves both."""

    async def head(self, repo: Path) -> str: ...

    async def dirty(self, repo: Path, *paths: str) -> tuple[str, ...]: ...

    async def created(self, repo: Path, *paths: str) -> tuple[str, ...]: ...

    async def open(self, repo: Path, path: Path, base: str) -> Path: ...

    async def close(self, path: Path) -> None: ...

    async def fingerprint(self, repo: Path) -> tuple[str, dict[str, str]]: ...

    async def changed(self, repo: Path, base: str, rel: str) -> tuple[str, ...]: ...

    async def overlay(self, source: Path, target: Path, rel: str) -> None: ...

    async def diff(self, sandbox: Path, base: str, rel: str) -> str: ...

    async def apply(self, repo: Path, patch: Path, *, check: bool = False, reverse: bool = False) -> bool: ...


@runtime_checkable
class ScannerPort(Protocol):
    """A security scan of one rendered folder, with the scanner at the install source `source` names."""

    async def scan(self, folder: Path, source: str) -> ScanResult: ...


@runtime_checkable
class TrialPort(Protocol):
    """The real harness raised fenced on a render of `nous`, asked what reached its fake model (`TrialService`)."""

    async def run(self, nous: NousPort, backend: str, capture: CapturePort) -> TrialReport: ...


@runtime_checkable
class EvalsPort(Protocol):
    """The evaluator's ledgers in an e-nous checkout: a skill's query and task sets, and where each was read."""

    async def queries(self, nous: Path, skill: str) -> tuple[QuerySet | None, str]: ...

    async def tasks(self, nous: Path, skill: str) -> tuple[TaskSet | None, str]: ...


##### PLANE CONTEXT #####
@dataclass(frozen=True, slots=True)
class PlaneState:
    """The resources of one plane run. Immutable; the ledger is the only thing that grows."""

    manifest: PlaneManifest
    paths: PlanePaths
    ledger: LedgerPort


@dataclass(frozen=True, slots=True)
class PlaneContext:
    """What one node run sees: the run, its own spec, and the subject it is scoped to (empty: the corpus)."""

    state: PlaneState
    spec: NodeSpec
    subject: str

    @property
    def workdir(self) -> Path:
        return self.state.paths.node(self.spec.id, self.subject)

    def param(self, key: str, default: str = "") -> str:
        return self.spec.params.get(key, default)

    def upstream(self, node: str) -> NodeRun | None:
        """The latest run of another node over this subject, or over the corpus when it is corpus-scoped."""
        return self.state.ledger.latest(node, self.subject) or self.state.ledger.latest(node)


@runtime_checkable
class PlaneNodePort(Protocol):
    """A node of a plane graph: its card, and one async call from its context to an outcome. Never raises for a
    verdict."""

    @property
    def card(self) -> NodeCard: ...

    async def run(self, context: PlaneContext) -> Outcome: ...
