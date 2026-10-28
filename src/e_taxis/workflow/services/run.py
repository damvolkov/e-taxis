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
from e_taxis.workflow.models.error import CommandError, RunFailedError, WorkflowError
from e_taxis.workflow.models.ports import RunState
from e_taxis.workflow.models.run import RunManifest, RunPaths, RunReport
from e_taxis.workflow.models.workflow import ParamType, Workflow
from e_taxis.workflow.services.step import LEAD, AnsweredStep, WorkflowStep

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from e_taxis.transpile.models.ports import NousPort
    from e_taxis.workflow.models.ports import AgentPort, CommandPort, HarnessPort, LedgerPort, LockPort
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

    async def _common_project(self, decl: Workflow, given: dict[str, str], cwd: Path) -> dict[str, str]:
        """`given` with every empty `project` kwarg made the git root of `cwd` — the terminal's project."""
        empty = [name for name, param in decl.params.items() if param.type is ParamType.PROJECT and not given.get(name)]
        match empty:
            case []:
                return given
            case _:
                pass
        try:
            root = (await self._command.run("git", "-C", str(cwd), "rev-parse", "--show-toplevel", limit=GIT)).strip()
        except CommandError as outside:
            msg = f"{decl.id}: {', '.join(empty)} is empty and {cwd} is in no git project — pass {empty[0]}=PATH"
            raise WorkflowError(msg) from outside
        return given | dict.fromkeys(empty, root)

    async def _one_manifest(self, paths: RunPaths, manifest: RunManifest) -> RunManifest:
        """The run's manifest: the one its folder holds, else this one, written once — the first step opens the run."""
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        try:
            async with await anyio.open_file(paths.manifest, "xb") as fresh:
                await fresh.write(msgspec.json.format(msgspec.json.encode(manifest)))
        except FileExistsError:
            return msgspec.json.decode(await anyio.Path(paths.manifest).read_bytes(), type=RunManifest)
        return manifest

    ############################################################

    ##### PUBLIC #####

    def reports(self, root: Path) -> Path:
        """Where a checkout's runs live."""
        return root / self._reports

    async def run(
        self,
        source: NousPort,
        ident: str,
        given: dict[str, str],
        notify: Callable[[NodeRun], None] | None = None,
        *,
        cwd: Path | None = None,
    ) -> RunReport:
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        params = reader.bind(decl, await self._common_project(decl, given, cwd or Path.cwd()))
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

    async def one(
        self,
        source: NousPort,
        ident: str,
        node: str,
        given: dict[str, str],
        rundir: Path,
        *,
        answer: Path | None = None,
        token: str = "",
        cwd: Path | None = None,
    ) -> NodeRun:
        """One step of a run a harness walks: `rundir` holds the run; its first step opens it with `given`. With
        `answer`, the step is a semantic one the harness's agent already answered."""
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        root = Path(tree.root)
        base = await self._run_head(root)
        paths = RunPaths(Path(await anyio.Path(rundir).resolve()))
        manifest = await self._one_manifest(
            paths,
            RunManifest(
                run_id=paths.root.name,
                workflow=ident,
                nous=str(root),
                base_sha=base,
                started=dt.datetime.now(dt.UTC),
                graph=graph,
                params=reader.bind(decl, await self._common_project(decl, given, cwd or Path.cwd())),
            ),
        )
        ledger = await self._ledgers(paths.ledger)
        port = (
            AnsweredStep(answer)
            if answer
            else WorkflowStep(self._command, self._agent, limit=self._limit, env={LOCK_ENV: token} if token else {})
        )
        state = RunState(manifest=manifest, paths=paths, ledger=ledger)
        return await DagExecutor(port, 1).one(state, node, kept=answer is None)

    async def launch(
        self, source: NousPort, ident: str, given: dict[str, str], harness: HarnessPort, *, cwd: Path
    ) -> RunReport:
        """The whole workflow walked by a harness, its run folder under `cwd`'s reports: the parameters checked
        first, the report rebuilt from the ledger the steps left, the declared output verified on disk."""
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        params = reader.bind(decl, await self._common_project(decl, given, cwd))
        now = dt.datetime.now(dt.UTC)
        rundir = self._reports / "workflows" / ident / f"{now:%Y%m%dT%H%M%SZ}-{ident}"
        paths = RunPaths(cwd / rundir)
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        actors = tuple(dict.fromkeys(step.actor or LEAD for step in graph if step.semantic))
        said = await harness.run(ident, {**params, "rundir": str(paths.root), "nous": tree.root}, actors, cwd=cwd)
        manifest = (
            msgspec.json.decode(await anyio.Path(paths.manifest).read_bytes(), type=RunManifest)
            if await anyio.Path(paths.manifest).is_file()
            else RunManifest(
                run_id=paths.root.name, workflow=ident, nous=tree.root, base_sha="", started=now, graph=graph
            )
        )
        runs = (await self._ledgers(paths.ledger)).runs() if await anyio.Path(paths.ledger).is_file() else ()
        report = RunReport(manifest=manifest, runs=runs, folder=str(paths.root))
        await anyio.Path(paths.report).write_text(f"{report.markdown}\n\n## The harness said\n\n{said}\n")
        wanted = [part.strip().replace("<rundir>", str(paths.root)) for part in decl.output.get("path", "").split("·")]
        missing = [path for path in wanted if path and not await anyio.Path(path).exists()]
        match missing:
            case []:
                return report
            case _:
                msg = f"{ident}: the harness ended without the declared output: {', '.join(missing)}"
                raise RunFailedError(msg)
