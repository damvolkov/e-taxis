"""commands.distill: `taxis distill <step>` — reverse-distill's deterministic steps, one command per workflow node.

The workflow (`core/tekton/workflows/reverse-distill/`) calls these as its `run` nodes with `--rundir {{rundir}}`
(and `--nous {{nous}}` where the step reads e-nous); each reads its parents' typed artifacts from the run's folder
and writes its own. The agent steps between them answer in JSON blocks; which steps those are is read from the
workflow's own output ports (`Mining`, `Judgements`, `Reviews`), never from an id written here. `guard` exits 3 when
there is nothing to distill: the workflow skips the rest at zero tokens."""

import json
from collections import Counter
from pathlib import Path, PurePosixPath

import anyio
import msgspec
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.nous import NousTree
from e_taxis.workflow.distill.drift import DistillDrift
from e_taxis.workflow.distill.grade import DistillGrade
from e_taxis.workflow.distill.graph import DistillGraph
from e_taxis.workflow.distill.inventory import DistillInventory
from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.distill.report import DistillReport
from e_taxis.workflow.distill.scope import DistillScope
from e_taxis.workflow.distill.store import DistillStore
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.distill import (
    PORTS,
    Candidate,
    Grade,
    Indexes,
    Inventory,
    Judgement,
    Manifest,
    Mining,
    Report,
    Review,
    RunMeta,
    Scope,
    Waiver,
)
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import DistillError
from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
MATRIX: str = "core/versioning/matrix.yaml"
SCHEMAS: str = "schemas"


##### UTILITIES #####
def say_artifact(console: Console, path: Path, line: str) -> None:
    console.out(f"{line}\nartifact: {path}", highlight=False)


def writers_of(tree: NousTree, workflow: str, model: str) -> tuple[str, ...]:
    """The steps of `workflow` whose output port is `model`: who answered what the next step reads."""
    match WorkflowReader(tree).load(workflow).writers(model):
        case ():
            msg = f"{workflow}: no step writes a {model}"
            raise DistillError(msg)
        case found:
            return found


def layout_of(tree: NousTree) -> dict[Entity, Path]:
    """Where each entity's instances live in this checkout: the folder its schema path puts `{id}` in."""
    known = {entity.value for entity in Entity}
    return {
        Entity(name): Path(spec["path"]).parent.parent
        for name, spec in tree.schema.get("entities", {}).items()
        if name in known
    }


def schema_text(name: str) -> bytes:
    """One port's JSON Schema, as the workflow's `schemas/` holds it."""
    return msgspec.json.format(msgspec.json.encode(msgspec.json.schema(PORTS[name])), indent=2) + b"\n"


async def blueprint_of(settings: TaxisSettings) -> Path:
    return Path(await anyio.Path(settings.taxis_distill_blueprint).expanduser())


##### COMMANDS #####
async def guard(
    *,
    rundir: Path,
    project: Path,
    branches: str = "",
    since: str = "",
    work: str = "",
    command: Inject[CommandPort],
    console: Inject[Console],
) -> None:
    """Fix the run's scope: the project, its branches and the base they grew from. Exit 3: nothing to distill.

    Args:
        rundir: the run's folder.
        project: the project's path.
        branches: branches, space-separated; empty = the current one.
        since: the base commit or ref; empty = the merge-base with main.
        work: what the human says was done and learned.
    """
    scope = await DistillScope(command).guard(project, tuple(branches.split()), since, work)
    path = await DistillStore(rundir).put("scope", scope)
    say_artifact(console, path, f"{scope.graph}: {', '.join(scope.branches)} since {scope.base[:12]}")


async def intake(*, rundir: Path, command: Inject[CommandPort], console: Inject[Console]) -> None:
    """List the branches' commits and touched files since the base.

    Args:
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    manifest = await DistillScope(command).intake(await store.get("scope", Scope))
    path = await store.put("manifest", manifest)
    say_artifact(console, path, f"{len(manifest.commits)} commits · {len(manifest.files)} files")


async def index(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    command: Inject[CommandPort],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Index e-nous, e-arkhetypo and the project in the code graph (incremental).

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    scope = await store.get("scope", Scope)
    indexes = await DistillGraph(command, settings.taxis_distill_graph).index(
        nous,
        settings.taxis_distill_blueprint,
        Path(scope.project),
        settings.taxis_distill_ref,
        settings.taxis_distill_cache,
    )
    path = await store.put("indexes", indexes)
    say_artifact(console, path, f"graph: {indexes.harness} · {indexes.blueprint} · {indexes.project}")


async def scan(
    *, rundir: Path, command: Inject[CommandPort], settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """The files the branches changed in the run's range (git), and the symbols the code graph says they impact.

    Args:
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    scope = await store.get("scope", Scope)
    changed = await DistillScope(command).changed(scope)
    deltas = await DistillGraph(command, settings.taxis_distill_graph).scan(scope, changed)
    path = await store.put("deltas", deltas)
    say_artifact(console, path, f"{len(deltas.changed)} files changed · {len(deltas.impacted)} symbols impacted")


async def drift(*, rundir: Path, command: Inject[CommandPort], console: Inject[Console]) -> None:
    """Run the project's own drift checks against the blueprint it materialized.

    Args:
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    found = await DistillDrift(command).check(Path((await store.get("scope", Scope)).project))
    line = f"{len(found.files)} drifted" if found.checked else "no drift checks in this project"
    say_artifact(console, await store.put("drift", found), line)


async def inventory(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    command: Inject[CommandPort],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Read the project against the published blueprint and the core's lib.md and MCP wiring, plane by plane.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    taker = DistillInventory(
        command, harness=nous, blueprint=await blueprint_of(settings), ref=settings.taxis_distill_ref
    )
    taken = await taker.take(await store.get("manifest", Manifest))
    planes = Counter(f.plane for f in taken.facts)
    fresh = sum(1 for f in taken.facts if f.fresh)
    line = " · ".join(f"{plane} {n}" for plane, n in planes.items()) or "nothing"
    said = f"{len(taken.facts)} facts ({fresh} fresh): {line} · {len(taken.stale)} behind its blueprint"
    say_artifact(console, await store.put("inventory", taken), said)


async def grade(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    command: Inject[CommandPort],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Read every miner's candidates through the model, propagate the contradictions and weigh each one.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store = DistillStore(rundir)
    tree = await GitNous(nous, None).load()
    sides = [await store.agent(node, Mining) for node in writers_of(tree, settings.taxis_distill_workflow, "Mining")]
    cap = settings.taxis_distill_candidates
    over = frozenset(c.id for side in sides for c in side.candidates[cap:])
    grader = DistillGrade(
        command,
        await VersionMatrix.load(nous / MATRIX),
        harness=nous,
        blueprint=await blueprint_of(settings),
        layout=layout_of(tree),
        scope=settings.taxis_distill_scope,
        ref=settings.taxis_distill_ref,
    )
    candidates, spread = await grader.propagate(DistillGrade.merge(*(side.candidates for side in sides)))
    grades = await grader.grade(candidates, over, spread)
    await store.put("waivers", tuple(w for side in sides for w in side.waived))
    await store.put("candidates", candidates)
    path = await store.put("grades", grades)
    rows = [
        {"candidate": g.candidate, "matrix": g.matrix, "reach": g.reach, "stop": g.stop, "propagated": g.propagated}
        for g in grades
    ]
    console.out(json.dumps(rows, ensure_ascii=False), highlight=False)
    live = sum(1 for g in grades if not g.stop)
    say_artifact(console, path, f"{len(grades)} candidates · {live} go to the judge · {len(grades) - live} stopped")


async def report(
    *, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Join verdicts and reviews to the graded candidates; write report.json, report.md and the briefs.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store, tree = DistillStore(rundir), await GitNous(nous, None).load()
    workflow = settings.taxis_distill_workflow
    scope, indexes = await store.get("scope", Scope), await store.get("indexes", Indexes)
    try:
        reviews = await store.agent(writers_of(tree, workflow, "Reviews")[0], tuple[Review, ...])
    except DistillError:
        reviews = ()
    meta = RunMeta(
        id=rundir.name,
        project=scope.project,
        branches=scope.branches,
        base=scope.base,
        work=scope.work,
        harness=indexes.heads.get(indexes.harness, ""),
        blueprint=indexes.heads.get(indexes.blueprint, ""),
        folder=str(rundir),
    )
    taken = await store.get("inventory", Inventory)
    reporter = DistillReport(blueprint=str(await blueprint_of(settings)), nous=str(nous))
    built = reporter.build(
        meta,
        candidates=await store.get("candidates", tuple[Candidate, ...]),
        grades=await store.get("grades", tuple[Grade, ...]),
        judgements=await store.agent(writers_of(tree, workflow, "Judgements")[0], tuple[Judgement, ...]),
        reviews=reviews,
        facts=taken.facts,
        waivers=await store.get("waivers", tuple[Waiver, ...]),
        stale=taken.stale,
    )
    await store.put("report", built)
    await anyio.Path(rundir / "briefs").mkdir(parents=True, exist_ok=True)
    _ = [await anyio.Path(path).write_text(brief) for path, brief in reporter.briefs(built).items()]
    text = reporter.render(built)
    await anyio.Path(rundir / "report.md").write_text(text)
    console.out(text, highlight=False)


async def ship(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    command: Inject[CommandPort],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Run, in order, the commands that apply the run's musts.

    Args:
        nous: the e-nous checkout the commands run in.
        rundir: the run's folder.
    """
    reporter = DistillReport(blueprint=str(await blueprint_of(settings)), nous=str(nous))
    commands = reporter.ship(await DistillStore(rundir).get("report", Report))
    said = [
        f"$ {line}\n" + await command.run("bash", "-lc", line, limit=settings.taxis_workflow_timeout, cwd=nous)
        for line in commands
    ]
    _ = [console.out(text, highlight=False) for text in said]
    console.out(f"shipped {len(commands)} must(s); shoulds stay in report.md for you", highlight=False)


async def schemas(
    *, nous: Nous = UNSET, check: bool = False, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Write the JSON Schema of every reverse-distill port into the workflow's `schemas/`; --check only compares.

    Args:
        nous: the e-nous checkout.
        check: write nothing; fail when a schema differs from its model.
    """
    tree = await GitNous(nous, None).load()
    path = tree.schema["entities"]["workflow"]["path"].replace("{id}", settings.taxis_distill_workflow)
    folder = nous / PurePosixPath(path).parent / SCHEMAS
    found = {
        name: await anyio.Path(folder / f"{name}.json").read_bytes()
        if await anyio.Path(folder / f"{name}.json").is_file()
        else b""
        for name in PORTS
    }
    stale = sorted(name for name, raw in found.items() if raw != schema_text(name))
    match (check, stale):
        case (True, []) | (False, []):
            console.out(f"schemas: {len(PORTS)} in sync in {folder}", highlight=False)
        case (True, _):
            msg = f"stale schemas in {folder}: {', '.join(stale)} — run `taxis distill schemas --nous {nous}`"
            raise DistillError(msg)
        case _:
            await anyio.Path(folder).mkdir(parents=True, exist_ok=True)
            _ = [await anyio.Path(folder / f"{name}.json").write_bytes(schema_text(name)) for name in stale]
            console.out(f"schemas: {len(stale)} written in {folder}", highlight=False)
