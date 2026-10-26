"""models.ports: what the workflow engine asks of the world — run a command, drive an agent, keep a ledger, run a step.

The context is part of the contract: a run's resources (manifest, paths, ledger) are fixed when it starts; the
evidence lives only in the ledger, append-only and typed. A step reads upstream evidence through its context."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.run import NodeRun, Outcome, Reply, RunManifest, RunPaths


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

    def latest(self, node: str) -> NodeRun | None: ...

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
