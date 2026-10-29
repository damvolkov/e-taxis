"""commands.compare: `taxis workflow radar-stack <step>` — radar-stack's deterministic steps, one command per node.

The workflow (`core/tekton/workflows/radar-stack/`) calls these as its `run` nodes with `--rundir {{rundir}}`; each
reads its parents' typed artifacts from `<rundir>/radar/` and writes its own. The agent steps between them (rivals,
weigh, verdict, adversary) answer in JSON blocks, read back through their models; which steps those are is read from
the workflow's own output ports (`Rivals`, `Plans`, `Verdicts`, `Reviews`), never from an id written here. The rank
that keeps every incumbent writes the final report itself and exits 3: nothing downstream is paid for."""

from pathlib import Path, PurePosixPath
from typing import Any

import anyio
import msgspec
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.assess.health import AssessHealth
from e_taxis.workflow.assess.stats import AssessStats
from e_taxis.workflow.assess.store import FOLDER, AssessStore
from e_taxis.workflow.commands.assess import SKIP, now_utc, topics_of
from e_taxis.workflow.commands.distill import say_artifact, writers_of
from e_taxis.workflow.compare.bench import CompareBench
from e_taxis.workflow.compare.health import CompareHealth
from e_taxis.workflow.compare.intake import CompareIntake
from e_taxis.workflow.compare.rank import CompareRank
from e_taxis.workflow.compare.report import CompareReport
from e_taxis.workflow.compare.stats import CompareStats
from e_taxis.workflow.models.compare import (
    PORTS,
    Healths,
    PairSamples,
    PairStats,
    Plans,
    Reviews,
    Rivals,
    Shortlist,
    Stack,
    Verdicts,
)
from e_taxis.workflow.models.error import CompareError, NothingError
from e_taxis.workflow.models.ports import ApiPort

##### DEFAULTS #####
SCHEMAS: str = "schemas"
REPORT: str = "report.md"


##### UTILITIES #####
async def answer_compare(nous: Path, settings: TaxisSettings, rundir: Path, model: str) -> Any:
    """The agent step's answer the workflow's ports say writes `model`, read through its model."""
    tree = await GitNous(nous, None).load()
    node = writers_of(tree, settings.taxis_compare_workflow, model)[0]
    return await AssessStore(rundir).agent(node, PORTS[model])


def schema_compare(name: str) -> bytes:
    """One port's JSON Schema, as the workflow's `schemas/` holds it."""
    return msgspec.json.format(msgspec.json.encode(msgspec.json.schema(PORTS[name])), indent=2) + b"\n"


async def write_compare(rundir: Path, settings: TaxisSettings, built: Any, console: Console) -> None:
    """radar/report.md and radar/compare.json, and the verdicts indexed in the state's compared.json."""
    reporter = CompareReport()
    text = reporter.render(built)
    ### never <rundir>/report.md: the engine writes its own run report there when the run ends.
    await anyio.Path(rundir / FOLDER / REPORT).write_text(text)
    await AssessStore(rundir).put("compare", built)
    index = await reporter.record(Path(await anyio.Path(settings.taxis_radar_state).expanduser()), built)
    console.out(f"{text}\nindexed: {index}", highlight=False)


##### COMMANDS #####
async def intake(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    project: Path,
    query: str = "",
    topic: str = "",
    console: Inject[Console],
) -> None:
    """Read what the repository declares: every dependency, its version, its manifest, where it is imported.

    Args:
        nous: the e-nous checkout (its radar.yaml names the topics).
        rundir: the run's folder.
        project: the repository.
        query: what to compare, as Damien wrote it.
        topic: a radar.yaml topic; empty = none.
    """
    found = await CompareIntake(await topics_of(nous)).read(project, query, topic)
    path = await AssessStore(rundir).put("stack", found)
    say_artifact(console, path, f"{len(found.dependencies)} dependencies in {', '.join(found.manifests)}")


async def health(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    api: Inject[ApiPort],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Every incumbent's and rival's dated health, and whether its hot path is Rust or C.

    Args:
        nous: the e-nous checkout (its workflow names the step that answered the rivals).
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    rivals: Rivals = await answer_compare(nous, settings, rundir, "Rivals")
    found = await CompareHealth(api, AssessHealth(api)).measure(rivals, now_utc())
    path = await store.put("healths", found)
    say_artifact(console, path, f"{len(found.subjects)} subjects measured at {found.measured_at}")


async def rank(*, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """Score incumbents and rivals on one rubric; keep, per incumbent, the best rival that beats it — or report that
    every incumbent is kept and exit 3.

    Args:
        nous: the e-nous checkout (its workflow names the step that answered the rivals).
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    rivals: Rivals = await answer_compare(nous, settings, rundir, "Rivals")
    shortlist = CompareRank(now_utc()).rank(rivals, await store.get("healths", Healths))
    path = await store.put("shortlist", shortlist)
    benched = [contest for contest in shortlist.contests if contest.rival]
    say_artifact(console, path, f"{len(benched)} of {len(shortlist.contests)} incumbents earn a bench")
    match benched:
        case []:
            built = CompareReport().build(
                await store.get("stack", Stack),
                shortlist,
                (Plans(pairs=()), PairStats(pairs=()), Verdicts(verdicts=()), Reviews(reviews=())),
                date=now_utc().date().isoformat(),
                path=str(rundir / FOLDER / REPORT),
            )
            await write_compare(rundir, settings, built, console)
            msg = "every incumbent is kept by the rubric: no rival earns a bench"
            raise NothingError(msg)
        case _:
            pass


async def bench(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    bench: str = "",
    runner: Inject[AssessBench],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Every shortlisted pair benched as radar-tech benches one: fenced, interleaved, raw samples kept.

    Args:
        nous: the e-nous checkout (its workflow names the step that wrote the plans).
        rundir: the run's folder.
        bench: `false` installs nothing and records every pair as not measured; empty = measure.
    """
    plans: Plans = await answer_compare(nous, settings, rundir, "Plans")
    found = await CompareBench(runner).run(plans, skip=bench.strip().lower() in SKIP, now=now_utc())
    path = await AssessStore(rundir).put("samples", found)
    runs = sum(len(arm.samples) for pair in found.pairs for arm in pair.samples.arms)
    say_artifact(console, path, f"{len(found.pairs)} pairs · {runs} samples kept")


async def stats(*, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """Per pair, the paired bootstrap interval of the difference against its threshold.

    Args:
        nous: the e-nous checkout (its workflow names the step that wrote the plans).
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    plans: Plans = await answer_compare(nous, settings, rundir, "Plans")
    found = CompareStats(AssessStats()).compare(plans, await store.get("samples", PairSamples))
    path = await store.put("stats", found)
    say_artifact(console, path, " · ".join(f"{pair.incumbent}: {pair.stats.outcome}" for pair in found.pairs))


async def report(
    *, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Write radar/report.md and radar/compare.json: per incumbent, the verdict as it stood after the adversary.

    Args:
        nous: the e-nous checkout (its workflow names the steps that answered).
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    answers = (
        await answer_compare(nous, settings, rundir, "Plans"),
        await store.get("stats", PairStats),
        await answer_compare(nous, settings, rundir, "Verdicts"),
        await answer_compare(nous, settings, rundir, "Reviews"),
    )
    built = CompareReport().build(
        await store.get("stack", Stack),
        await store.get("shortlist", Shortlist),
        answers,
        date=now_utc().date().isoformat(),
        path=str(rundir / FOLDER / REPORT),
    )
    await write_compare(rundir, settings, built, console)


async def schemas(
    *, nous: Nous = UNSET, check: bool = False, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Write the JSON Schema of every radar-stack port into the workflow's `schemas/`; --check only compares.

    Args:
        nous: the e-nous checkout.
        check: write nothing; fail when a schema differs from its model.
    """
    tree = await GitNous(nous, None).load()
    path = tree.schema["entities"]["workflow"]["path"].replace("{id}", settings.taxis_compare_workflow)
    folder = nous / PurePosixPath(path).parent / SCHEMAS
    found = {
        name: await anyio.Path(folder / f"{name}.json").read_bytes()
        if await anyio.Path(folder / f"{name}.json").is_file()
        else b""
        for name in PORTS
    }
    stale = sorted(name for name, raw in found.items() if raw != schema_compare(name))
    match (check, stale):
        case (_, []):
            console.out(f"schemas: {len(PORTS)} in sync in {folder}", highlight=False)
        case (True, _):
            msg = f"stale schemas in {folder}: {', '.join(stale)} — run `taxis workflow radar-stack schemas --nous {nous}`"
            raise CompareError(msg)
        case _:
            await anyio.Path(folder).mkdir(parents=True, exist_ok=True)
            _ = [await anyio.Path(folder / f"{name}.json").write_bytes(schema_compare(name)) for name in stale]
            console.out(f"schemas: {len(stale)} written in {folder}", highlight=False)
