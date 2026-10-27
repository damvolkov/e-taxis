"""services.plane: one evaluation or enhancement, end to end — subjects, manifest, folder, lock, execute, report.

The evaluator measures the checkout as it stands — or, asked for an enhancer run's `candidate`, a clone at that run's
base with its patches applied: an evaluation that reports on a change measures the change, whether `promote` ran or
idled (docs/workflow.md §5, defect 7). The enhancer acts only on a reason — the needs of an evaluation (`--from`),
your directive, or your working-tree edits (`--manual`) — refuses a dirty subject it was not told to take, and exits
3 when no subject has a need. Every run is pinned to the checkout's HEAD in `run.json`, held under the checkout's run
lock (re-entered when a parent workflow holds it), executed, and reported from its ledger; its clone is removed
unless kept. Runs live flat under `<nous>/<reports>/<run>/`; `latest` is the newest of a plane and target."""

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.executor import SubjectExecutor
from e_taxis.workflow.engine.reader import PlaneReader
from e_taxis.workflow.engine.subject import NousSubject
from e_taxis.workflow.models.error import IdleError, PlaneError, ReasonError
from e_taxis.workflow.models.metrics import NeedsMetrics
from e_taxis.workflow.models.plane import Plane, PlaneManifest, PlanePaths
from e_taxis.workflow.models.ports import PlaneState
from e_taxis.workflow.models.report import PlaneReport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from e_taxis.workflow.models.metrics import Owner
    from e_taxis.workflow.models.plane import Cadence, Target
    from e_taxis.workflow.models.ports import LedgerPort, LockPort, PlaneNodePort, SandboxPort
    from e_taxis.workflow.models.run import NodeRun

##### DEFAULTS #####
LOCK: str = ".lock"
LATEST: str = "latest"
MANIFEST: str = "run.json"
LEDGER: str = "ledger.jsonl"
NEEDS: str = "needs"
PATCHES: str = "patches"


##### TYPES #####
class PlaneRun:
    """Every port injected; `reports` is relative to the checkout unless absolute; `backend` the render measured."""

    __slots__ = ("_backend", "_concurrency", "_ledgers", "_lock", "_nodes", "_reports", "_sandbox")

    def __init__(
        self,
        nodes: Mapping[str, PlaneNodePort],
        sandbox: SandboxPort,
        lock: LockPort,
        ledgers: Callable[[Path], Awaitable[LedgerPort]],
        *,
        concurrency: int,
        reports: Path,
        backend: str,
    ) -> None:
        self._nodes = nodes
        self._sandbox = sandbox
        self._lock = lock
        self._ledgers = ledgers
        self._concurrency = concurrency
        self._reports = reports
        self._backend = backend

    ##### PRIVATE METHODS #####

    def _common_reader(self) -> PlaneReader:
        return PlaneReader({use: node.card for use, node in self._nodes.items()})

    async def _common_manifest(
        self,
        root: Path,
        plane: Plane,
        target: Target,
        subjects: tuple[str, ...],
        cadence: Cadence,
        *,
        source: str = "",
        directive: str = "",
        manual: bool = False,
    ) -> PlaneManifest:
        places = NousSubject(await GitNous(root, None).load())
        base = await self._sandbox.head(root)
        now = dt.datetime.now(dt.UTC)
        return PlaneManifest(
            run_id=f"{now:%Y%m%dT%H%M%SZ}-{plane}-{target}-{base[:7]}",
            plane=plane,
            target=target,
            subjects=subjects,
            cadence=cadence,
            nous=str(root),
            tree=str(root),
            base_sha=base,
            backend=self._backend,
            started=now,
            graph=self._common_reader().read(plane, target),
            places={subject: places.place(target, subject) for subject in subjects},
            source=source,
            directive=directive,
            manual=manual,
        )

    async def _common_execute(
        self, manifest: PlaneManifest, paths: PlanePaths, *, keep: bool, notify: Callable[[NodeRun], None] | None
    ) -> PlaneReport:
        await anyio.Path(paths.root).mkdir(parents=True, exist_ok=True)
        await anyio.Path(paths.manifest).write_bytes(msgspec.json.format(msgspec.json.encode(manifest)))
        ledger = await self._ledgers(paths.ledger)
        root = Path(manifest.nous)
        async with self._lock.hold(self.reports(root) / LOCK, f"{manifest.plane} {manifest.run_id}"):
            try:
                state = PlaneState(manifest=manifest, paths=paths, ledger=ledger)
                runs = await SubjectExecutor(self._nodes, self._concurrency, notify).run(state)
            finally:
                _ = keep or await self._sandbox.close(paths.sandbox)
        report = PlaneReport(manifest=manifest, runs=runs, folder=str(paths.root))
        await anyio.Path(paths.report).write_text(report.markdown)
        return report

    @staticmethod
    def _folder_match(name: str, plane: Plane | None, target: Target | None) -> bool:
        """Whether a run id (`<UTC>-<plane>-<target>-<sha7>`) is of `plane` and `target`, either left open."""
        _, ran, measured, _ = (*name.split("-", 3), "", "", "")[:4]
        return (plane is None or ran == plane) and (target is None or measured == target)

    async def _evaluate_candidate(
        self, root: Path, candidate: str, target: Target, paths: PlanePaths, subjects: tuple[str, ...]
    ) -> tuple[str, tuple[str, ...]]:
        """The enhancer run's candidate rebuilt in this run's clone: its base, each subject's patch applied. The run
        id, and the subjects that had a patch."""
        folder = await self.folder(root, candidate, Plane.ENHANCER, target)
        enhanced = msgspec.json.decode(await anyio.Path(folder / MANIFEST).read_bytes(), type=PlaneManifest)
        await self._sandbox.open(root, paths.sandbox, enhanced.base_sha)
        patches = {subject: folder / PATCHES / target.value / f"{subject}.patch" for subject in subjects}
        present = tuple([subject for subject, patch in patches.items() if await anyio.Path(patch).is_file()])
        refused = [s for s in present if not await self._sandbox.apply(paths.sandbox, patches[s], check=True)]
        match refused:
            case []:
                _ = [await self._sandbox.apply(paths.sandbox, patches[subject]) for subject in present]
                return enhanced.run_id, present
            case _:
                msg = f"{enhanced.run_id}: the patch of {', '.join(refused)} does not apply to its own base"
                raise PlaneError(msg)

    async def _enhance_needy(self, root: Path, source: str, owner: Owner | None) -> tuple[str, ...]:
        """The subjects the source evaluation found a need for — of `owner` when named."""
        ledger = await self._ledgers(self.reports(root) / source / LEDGER)
        return tuple(
            sorted(
                {
                    run.subject
                    for run in ledger.runs()
                    if run.node == NEEDS
                    and isinstance(run.metrics, NeedsMetrics)
                    and any(owner is None or need.owner is owner for need in run.metrics.needs)
                }
            )
        )

    @staticmethod
    def _enhance_reason(source: str, directive: str, ids: tuple[str, ...], *, manual: bool) -> None:
        match (bool(source or directive or manual), bool(directive) and not ids):
            case (False, _):
                msg = "an enhancement needs a reason: --from <evaluation>, --directive or --manual"
                raise ReasonError(msg)
            case (_, True):
                msg = "a --directive names the subjects it is for"
                raise ReasonError(msg)
            case _:
                pass

    ############################################################

    ##### PUBLIC #####

    def reports(self, root: Path) -> Path:
        """Where a checkout's runs live."""
        return root / self._reports

    def describe(self, plane: Plane, target: Target | None = None) -> str:
        return self._common_reader().describe(plane, target)

    async def folder(self, root: Path, run: str, plane: Plane | None = None, target: Target | None = None) -> Path:
        """A run's folder by id, or `latest` — the newest of a plane (and a target) when named."""
        reports = self.reports(root)
        found = sorted([path.parent.name async for path in anyio.Path(reports).glob(f"*/{MANIFEST}")])
        match (run, [name for name in found if self._folder_match(name, plane, target)]):
            case (str() as wanted, _) if wanted != LATEST and wanted in found:
                return reports / wanted
            case (str() as wanted, [*_, newest]) if wanted == LATEST:
                return reports / newest
            case _:
                msg = f"no {plane or 'plane'} {target or ''} run {run!r} under {reports}"
                raise PlaneError(msg)

    async def load(self, folder: Path) -> PlaneReport:
        """A run, rebuilt from its manifest and its ledger alone."""
        manifest = msgspec.json.decode(await anyio.Path(folder / MANIFEST).read_bytes(), type=PlaneManifest)
        ledger = await self._ledgers(folder / LEDGER)
        return PlaneReport(manifest=manifest, runs=ledger.runs(), folder=str(folder))

    async def evaluate(
        self,
        root: Path,
        target: Target,
        ids: tuple[str, ...],
        cadence: Cadence,
        *,
        candidate: str = "",
        keep: bool = False,
        notify: Callable[[NodeRun], None] | None = None,
    ) -> PlaneReport:
        """Measure `target`'s subjects (all, or `ids`) in the checkout — or in an enhancer run's candidate."""
        subjects = NousSubject(await GitNous(root, None).load()).all(target, ids)
        manifest = await self._common_manifest(root, Plane.EVALUATOR, target, subjects, cadence)
        paths = PlanePaths(self.reports(root) / manifest.run_id)
        match candidate:
            case "":
                return await self._common_execute(manifest, paths, keep=keep, notify=notify)
            case _:
                run, patched = await self._evaluate_candidate(root, candidate, target, paths, subjects)
                measured = msgspec.structs.replace(manifest, tree=str(paths.sandbox), candidate=run, patched=patched)
                return await self._common_execute(measured, paths, keep=keep, notify=notify)

    async def enhance(
        self,
        root: Path,
        target: Target,
        ids: tuple[str, ...],
        cadence: Cadence,
        *,
        source: str = "",
        directive: str = "",
        manual: bool = False,
        owner: Owner | None = None,
        keep: bool = False,
        notify: Callable[[NodeRun], None] | None = None,
    ) -> PlaneReport:
        """Enhance `target`'s subjects in a sandbox on a reason; write their verdicts and patches."""
        self._enhance_reason(source, directive, ids, manual=manual)
        origin = (await self.folder(root, source, Plane.EVALUATOR, target)).name if source else ""
        places = NousSubject(await GitNous(root, None).load())
        subjects = places.all(target, ids) if ids else await self._enhance_needy(root, origin, owner)
        base = await self._sandbox.head(root)
        dirty = [s for s in subjects if await self._sandbox.changed(root, base, places.place(target, s))]
        match (bool(dirty) and not manual, subjects):
            case (True, _):
                msg = f"uncommitted edits in {', '.join(dirty)}: commit them, or pass --manual to include them"
                raise ReasonError(msg)
            case (_, ()):
                msg = f"nothing to enhance: {origin or 'no evaluation'} states no need"
                raise IdleError(msg)
            case _:
                pass
        manifest = await self._common_manifest(
            root, Plane.ENHANCER, target, subjects, cadence, source=origin, directive=directive, manual=manual
        )
        paths = PlanePaths(self.reports(root) / manifest.run_id)
        return await self._common_execute(manifest, paths, keep=keep, notify=notify)
