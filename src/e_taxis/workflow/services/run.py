"""services.run: one workflow run, end to end — read, bind, pin, lock, execute, report.

The workflow is read from the e-nous checkout as it stands (the transpiler's reader, envelopes resolved), its
parameters bound (an undeclared one is refused before anything runs), the run pinned to the checkout's HEAD and given
its folder under `<nous>/<reports>/workflows/<id>/`. Only then is the lock taken — waited for, not refused — and the
graph executed. The report is written from the ledger whatever happened; deciding what a broken step means for the
exit code is the caller's."""

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.workflow.engine.executor import DagExecutor
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.error import CommandError
from e_taxis.workflow.models.ports import RunState
from e_taxis.workflow.models.run import RunManifest, RunPaths, RunReport
from e_taxis.workflow.services.step import WorkflowStep

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from e_taxis.transpile.models.ports import NousPort
    from e_taxis.workflow.models.ports import AgentPort, CommandPort, LedgerPort, LockPort
    from e_taxis.workflow.models.run import NodeRun

##### DEFAULTS #####
LOCK: str = ".lock"
LOCK_ENV: str = "TAXIS_LOCK"
GIT: float = 30.0


##### TYPES #####
class WorkflowRun:
    """Every port is injected; `reports` is relative to the checkout unless absolute."""

    __slots__ = ("_agent", "_command", "_concurrency", "_ledgers", "_limit", "_lock", "_reports")

    def __init__(
        self,
        command: CommandPort,
        agent: AgentPort,
        lock: LockPort,
        ledgers: Callable[[Path], Awaitable[LedgerPort]],
        *,
        concurrency: int,
        limit: float,
        reports: Path,
    ) -> None:
        self._command = command
        self._agent = agent
        self._lock = lock
        self._ledgers = ledgers
        self._concurrency = concurrency
        self._limit = limit
        self._reports = reports

    ##### PRIVATE METHODS #####

    async def _run_head(self, root: Path) -> str:
        """The checkout's HEAD; empty when it is no git checkout."""
        try:
            return (await self._command.run("git", "-C", str(root), "rev-parse", "HEAD", limit=GIT)).strip()
        except CommandError:
            return ""

    ############################################################

    ##### PUBLIC #####

    def reports(self, root: Path) -> Path:
        """Where a checkout's runs live."""
        return root / self._reports

    async def run(
        self, source: NousPort, ident: str, given: dict[str, str], notify: Callable[[NodeRun], None] | None = None
    ) -> RunReport:
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        params = reader.bind(decl, given)
        root = Path(tree.root)
        base = await self._run_head(root)
        now = dt.datetime.now(dt.UTC)
        run_id = f"{now:%Y%m%dT%H%M%SZ}-workflow-{ident}-{base[:7] or 'worktree'}"
        manifest = RunManifest(
            run_id=run_id, workflow=ident, nous=str(root), base_sha=base, started=now, graph=graph, params=params
        )
        paths = RunPaths(self.reports(root) / "workflows" / ident / run_id)
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await anyio.Path(paths.manifest).write_bytes(msgspec.json.format(msgspec.json.encode(manifest)))
        ledger = await self._ledgers(paths.ledger)
        async with self._lock.hold(self.reports(root) / LOCK, f"workflow run {run_id}") as token:
            step = WorkflowStep(self._command, self._agent, limit=self._limit, env={LOCK_ENV: token})
            state = RunState(manifest=manifest, paths=paths, ledger=ledger)
            runs = await DagExecutor(step, self._concurrency, notify).run(state)
        report = RunReport(manifest=manifest, runs=runs, folder=str(paths.root))
        await anyio.Path(paths.report).write_text(report.markdown)
        return report
