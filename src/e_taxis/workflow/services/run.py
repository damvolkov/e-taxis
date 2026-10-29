"""services.run: one workflow run, end to end — read, bind, pin, lock, execute, report.

The workflow is read from the e-nous checkout as it stands (the transpiler's reader, envelopes resolved), its
parameters bound (an undeclared one is refused before anything runs), the run pinned to the checkout's HEAD and given
its folder under `<nous>/<reports>/workflows/<id>/`. Only then is the lock taken — waited for, not refused — and the
graph executed. The report is written from the ledger whatever happened; deciding what a broken step means for the
exit code is the caller's."""

import asyncio
import datetime as dt
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import anyio
import msgspec

from e_taxis.workflow.engine.executor import DagExecutor
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.error import CommandError, RunFailedError, WorkflowError
from e_taxis.workflow.models.ports import RunState
from e_taxis.workflow.models.run import NodeRun, RunManifest, RunPaths, RunReport, Status
from e_taxis.workflow.models.workflow import ParamType, Workflow, items_workflow
from e_taxis.workflow.services.step import LEAD, AnsweredStep, WorkflowStep

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import NousPort
    from e_taxis.workflow.models.graph import GraphSpec
    from e_taxis.workflow.models.ports import AgentPort, CommandPort, HarnessPort, LedgerPort, LockPort
    from e_taxis.workflow.services.kwargs import WorkflowKwargs

##### DEFAULTS #####
LOCK: str = ".lock"
LOCK_ENV: str = "TAXIS_LOCK"
### the step a small model reads the query in, before the graph: recorded like any other.
KWARGS: str = "kwargs"
### a fanned run keeps its children under its own folder.
EACH: str = "each"
SLUG: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9._-]+")
GIT: float = 30.0


##### TYPES #####
class WorkflowRun:
    """Every port is injected; `reports` is relative to the checkout unless absolute."""

    __slots__ = ("_agent", "_command", "_concurrency", "_kwargs", "_ledgers", "_limit", "_lock", "_reports")

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
        kwargs: WorkflowKwargs | None = None,
    ) -> None:
        self._kwargs = kwargs
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

    async def _common_params(
        self, tree: NousTree, decl: Workflow, given: dict[str, str], cwd: Path
    ) -> tuple[dict[str, str], tuple[str, int, tuple[str, ...]]]:
        """The run's kwargs: the project resolved, what `query` states read by a small model, then the typed bind;
        and how they were read — the tier, its tokens and the kwargs it filled (empty when no model was asked)."""
        rooted = await self._common_project(decl, given, cwd)
        topics = tuple((tree.config.get("tekton", {}).get("soa") or {}).get("topics") or {})
        filled, tier, tokens = (
            await self._kwargs.fill(decl, rooted, Path(tree.root), topics) if self._kwargs else (rooted, "", 0)
        )
        read = tuple(name for name in filled if name not in rooted)
        return WorkflowReader(tree).bind(decl, filled), (tier, tokens, read)

    @staticmethod
    async def _common_record(ledger: LedgerPort, run_id: str, read: tuple[str, int, tuple[str, ...]]) -> None:
        """The `kwargs` step in the ledger, when a model read the query."""
        tier, tokens, names = read
        match tier:
            case "":
                return
            case _:
                now = dt.datetime.now(dt.UTC)
                reason = f"read {', '.join(names) or 'nothing'} from query"
                await ledger.append(
                    NodeRun(
                        run_id=run_id,
                        node=KWARGS,
                        status=Status.OK,
                        started=now,
                        ended=now,
                        input_hash="",
                        output_hash="",
                        reason=reason,
                        tokens=tokens,
                        runner=tier,
                    )
                )

    async def _one_manifest(self, paths: RunPaths, manifest: RunManifest) -> RunManifest:
        """The run's manifest: the one its folder holds, else this one, written once — the first step opens the run."""
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        try:
            async with await anyio.open_file(paths.manifest, "xb") as fresh:
                await fresh.write(msgspec.json.format(msgspec.json.encode(manifest)))
        except FileExistsError:
            return msgspec.json.decode(await anyio.Path(paths.manifest).read_bytes(), type=RunManifest)
        return manifest

    async def _run_graph(
        self,
        state: tuple[RunManifest, RunPaths],
        token: str,
        read: tuple[str, int, tuple[str, ...]],
        notify: Callable[[NodeRun], None] | None,
    ) -> RunReport:
        """One run's graph in its folder: manifest, ledger, the steps, its report."""
        manifest, paths = state
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await anyio.Path(paths.manifest).write_bytes(msgspec.json.format(msgspec.json.encode(manifest)))
        ledger = await self._ledgers(paths.ledger)
        await self._common_record(ledger, manifest.run_id, read)
        step = WorkflowStep(self._command, self._agent, limit=self._limit, env={LOCK_ENV: token})
        runs = await DagExecutor(step, self._concurrency, notify).run(
            RunState(manifest=manifest, paths=paths, ledger=ledger)
        )
        read_runs = tuple(run for run in ledger.runs() if run.node == KWARGS)
        report = RunReport(manifest=manifest, runs=(*read_runs, *runs), folder=str(paths.root))
        await anyio.Path(paths.report).write_text(report.markdown)
        return report

    @staticmethod
    def _run_each(
        manifest: RunManifest, paths: RunPaths, each: str, items: tuple[str, ...]
    ) -> list[tuple[RunManifest, RunPaths]]:
        """One run per item: the parent's manifest with the item as the `each` kwarg, a folder of its own under the
        parent's `each/`."""
        return [
            (
                msgspec.structs.replace(
                    manifest, run_id=f"{manifest.run_id}-{k}", params={**manifest.params, each: item}
                ),
                RunPaths(paths.root / EACH / f"{k}-{SLUG.sub('-', item).strip('-')[:40]}"),
            )
            for k, item in enumerate(items, 1)
        ]

    @staticmethod
    def _run_join(
        manifest: RunManifest, paths: RunPaths, each: str, children: list[RunReport]
    ) -> tuple[RunReport, str]:
        """The parent's report: every child's steps under its item, then one row per item and where its report is."""
        runs = tuple(
            msgspec.structs.replace(run, node=f"{k}·{run.node}")
            for k, child in enumerate(children, 1)
            for run in child.runs
        )
        report = RunReport(manifest=manifest, runs=runs, folder=str(paths.root))
        rows = "\n".join(
            f"| {child.manifest.params[each]} | {'broken' if child.broken else 'ok'} | {child.folder}/report.md |"
            for child in children
        )
        return msgspec.structs.replace(
            report, folder=str(paths.root)
        ), f"## each {each}\n\n| {each} | run | report |\n|---|---|---|\n{rows}\n"

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
        """One run of the graph — or, when the workflow declares `each` and its list holds several items, one run per
        item, in parallel under one lock, joined in the parent's report."""
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        params, read = await self._common_params(tree, decl, given, cwd or Path.cwd())
        root = Path(tree.root)
        base = await self._run_head(root)
        now = dt.datetime.now(dt.UTC)
        run_id = f"{now:%Y%m%dT%H%M%SZ}-workflow-{ident}-{base[:7] or 'worktree'}"
        manifest = RunManifest(
            run_id=run_id, workflow=ident, nous=str(root), base_sha=base, started=now, graph=graph, params=params
        )
        paths = RunPaths(self.reports(root) / "workflows" / ident / run_id)
        items = items_workflow(params.get(decl.each, "")) if decl.each else ()
        async with self._lock.hold(self.reports(root) / LOCK, f"workflow run {run_id}") as token:
            match len(items) > 1:
                case False:
                    return await self._run_graph((manifest, paths), token, read, notify)
                case _:
                    async with asyncio.TaskGroup() as group:
                        tasks = [
                            group.create_task(self._run_graph(child, token, read, notify))
                            for child in self._run_each(manifest, paths, decl.each, items)
                        ]
        report, table = self._run_join(manifest, paths, decl.each, [task.result() for task in tasks])
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await anyio.Path(paths.manifest).write_bytes(msgspec.json.format(msgspec.json.encode(manifest)))
        await anyio.Path(paths.report).write_text(f"{table}\n{report.markdown}")
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
        opened = await anyio.Path(paths.manifest).is_file()
        params, read = ({}, ("", 0, ())) if opened else await self._common_params(tree, decl, given, cwd or Path.cwd())
        manifest = await self._one_manifest(
            paths,
            RunManifest(
                run_id=paths.root.name,
                workflow=ident,
                nous=str(root),
                base_sha=base,
                started=dt.datetime.now(dt.UTC),
                graph=graph,
                params=params,
            ),
        )
        ledger = await self._ledgers(paths.ledger)
        await self._common_record(ledger, manifest.run_id, read)
        port = (
            AnsweredStep(answer)
            if answer
            else WorkflowStep(self._command, self._agent, limit=self._limit, env={LOCK_ENV: token} if token else {})
        )
        state = RunState(manifest=manifest, paths=paths, ledger=ledger)
        return await DagExecutor(port, 1).one(state, node, kept=answer is None)

    async def _launch_one(
        self,
        tree: NousTree,
        decl: Workflow,
        graph: GraphSpec,
        state: tuple[dict[str, str], RunPaths, tuple[str, int, tuple[str, ...]]],
        *,
        harness: HarnessPort,
        cwd: Path,
    ) -> tuple[RunReport, list[str]]:
        """One walk by the harness in its folder; its report, and the declared outputs it did not leave."""
        params, paths, read = state
        now = dt.datetime.now(dt.UTC)
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await self._common_record(await self._ledgers(paths.ledger), paths.root.name, read)
        actors = tuple(dict.fromkeys(step.actor or LEAD for step in graph if step.semantic))
        said = await harness.run(decl.id, {**params, "rundir": str(paths.root), "nous": tree.root}, actors, cwd=cwd)
        manifest = (
            msgspec.json.decode(await anyio.Path(paths.manifest).read_bytes(), type=RunManifest)
            if await anyio.Path(paths.manifest).is_file()
            else RunManifest(
                run_id=paths.root.name, workflow=decl.id, nous=tree.root, base_sha="", started=now, graph=graph
            )
        )
        runs = (await self._ledgers(paths.ledger)).runs() if await anyio.Path(paths.ledger).is_file() else ()
        report = RunReport(manifest=manifest, runs=runs, folder=str(paths.root))
        await anyio.Path(paths.report).write_text(f"{report.markdown}\n\n## The harness said\n\n{said}\n")
        wanted = [part.strip().replace("<rundir>", str(paths.root)) for part in decl.output.get("path", "").split("·")]
        return report, [path for path in wanted if path and not await anyio.Path(path).exists()]

    async def launch(
        self, source: NousPort, ident: str, given: dict[str, str], harness: HarnessPort, *, cwd: Path
    ) -> RunReport:
        """The whole workflow walked by a harness, its run folder under `cwd`'s reports: the parameters checked
        first, the report rebuilt from the ledger the steps left, the declared output verified on disk — one walk
        per item, in parallel, when the workflow declares `each` and its list holds several."""
        tree = await source.load()
        reader = WorkflowReader(tree)
        graph, decl = reader.read(ident)
        params, read = await self._common_params(tree, decl, given, cwd)
        now = dt.datetime.now(dt.UTC)
        paths = RunPaths(cwd / self._reports / "workflows" / ident / f"{now:%Y%m%dT%H%M%SZ}-{ident}")
        items = items_workflow(params.get(decl.each, "")) if decl.each else ()
        manifest = RunManifest(
            run_id=paths.root.name, workflow=ident, nous=tree.root, base_sha="", started=now, graph=graph, params=params
        )
        children = (
            [
                (child.params, child_paths, read)
                for child, child_paths in self._run_each(manifest, paths, decl.each, items)
            ]
            if len(items) > 1
            else [(params, paths, read)]
        )
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(self._launch_one(tree, decl, graph, state, harness=harness, cwd=cwd))
                for state in children
            ]
        walked = [task.result() for task in tasks]
        report = walked[0][0] if len(walked) == 1 else await self._launch_join(manifest, paths, decl.each, walked)
        match [path for _, missing in walked for path in missing]:
            case []:
                return report
            case missing:
                msg = f"{ident}: the harness ended without the declared output: {', '.join(missing)}"
                raise RunFailedError(msg)

    async def _launch_join(
        self, manifest: RunManifest, paths: RunPaths, each: str, walked: list[tuple[RunReport, list[str]]]
    ) -> RunReport:
        report, table = self._run_join(manifest, paths, each, [child for child, _ in walked])
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await anyio.Path(paths.report).write_text(f"{table}\n{report.markdown}")
        return report
