"""commands.assess: `taxis workflow soa-assess <step>` — soa-assess's deterministic steps, one command per node.

The workflow (`core/tekton/workflows/soa-assess/`) calls these as its `run` nodes with `--rundir {{rundir}}`; each
reads its parents' typed artifacts from `<rundir>/soa/` and writes its own. The agent steps between them (upstream,
weigh, verdict, adversary) answer in JSON blocks, read back through their models; which steps those are is read from
the workflow's own output ports (`Plan`, `Verdict`, `Review`), never from an id written here — and the workflow is
found where every command finds the brain (`--nous`, else the locator's ladder: a step runs in the checkout)."""

import datetime as dt
from pathlib import Path, PurePosixPath
from typing import Any

import anyio
import eserde
import msgspec
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.assess.health import AssessHealth
from e_taxis.workflow.assess.intake import AssessIntake
from e_taxis.workflow.assess.inventory import AssessInventory
from e_taxis.workflow.assess.report import KPIS, AssessReport
from e_taxis.workflow.assess.stats import AssessStats
from e_taxis.workflow.assess.store import FOLDER, AssessStore
from e_taxis.workflow.commands.distill import say_artifact, writers_of
from e_taxis.workflow.models.assess import (
    PORTS,
    Candidate,
    Health,
    Plan,
    Review,
    Samples,
    Stats,
    Verdict,
)
from e_taxis.workflow.models.error import AssessError
from e_taxis.workflow.models.ports import ApiPort

##### DEFAULTS #####
SOA: str = "core/tekton/config/soa.yaml"
SCHEMAS: str = "schemas"
SKIP: frozenset[str] = frozenset({"false", "no", "0", "off"})


##### UTILITIES #####
async def topics_of(nous: Path) -> dict[str, tuple[str, ...]]:
    """soa.yaml's topics, each with its keyword phrases."""
    path = anyio.Path(nous / SOA)
    found: Any = eserde.loads(await path.read_text(), format=eserde.Format.YAML) if await path.is_file() else {}
    return {
        name: tuple(map(str, (spec or {}).get("keywords") or ())) for name, spec in (found.get("topics") or {}).items()
    }


async def answer_of(nous: Path, settings: TaxisSettings, rundir: Path, model: str) -> Any:
    """The agent step's answer the workflow's ports say writes `model`, read through its model."""
    tree = await GitNous(nous, None).load()
    node = writers_of(tree, settings.taxis_assess_workflow, model)[0]
    return await AssessStore(rundir).agent(node, PORTS[model])


def schema_text(name: str) -> bytes:
    """One port's JSON Schema, as the workflow's `schemas/` holds it."""
    return msgspec.json.format(msgspec.json.encode(msgspec.json.schema(PORTS[name])), indent=2) + b"\n"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


##### COMMANDS #####
async def intake(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    tech: str,
    topic: str = "",
    api: Inject[ApiPort],
    console: Inject[Console],
) -> None:
    """Resolve the technology: a URL to its repository and package, a name to its registry entry.

    Args:
        nous: the e-nous checkout (its soa.yaml names the topics).
        rundir: the run's folder.
        tech: a repository URL, a registry URL or a bare package name.
        topic: a soa.yaml topic; empty = none.
    """
    found = await AssessIntake(api, await topics_of(nous)).resolve(tech, topic)
    path = await AssessStore(rundir).put("candidate", found)
    source = " · ".join(
        part for part in (found.repo, f"{found.registry} {found.package}" if found.registry else "") if part
    )
    say_artifact(console, path, f"{found.name}: {source}" + "".join(f"\n  note: {note}" for note in found.notes))


async def inventory(
    *, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """What lives here in the candidate's domain: lib.md rows, stacks, MCP servers, the live trees, past reports.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    candidate = await store.get("candidate", Candidate)
    claude = settings.claude_config_dir or Path.home() / ".claude"
    reports = nous / settings.taxis_workflow_reports / "workflows" / settings.taxis_assess_workflow
    taker = AssessInventory(nous, trees=(settings.taxis_workflow_opencode.expanduser(), claude), reports=reports)
    taken = await taker.take(candidate, (await topics_of(nous)).get(candidate.topic, ()))
    path = await store.put("inventory", taken)
    say_artifact(console, path, f"{len(taken.rows)} rows in the domain · {len(taken.assessed)} past assessments")


async def health(*, rundir: Path, api: Inject[ApiPort], console: Inject[Console]) -> None:
    """The candidate's dated health KPIs from no-auth sources; a source that fails is named, never guessed.

    Args:
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    found = await AssessHealth(api).measure(await store.get("candidate", Candidate), now_utc())
    path = await store.put("health", found)
    measured = sum(getattr(found, kpi) is not None for kpi in KPIS)
    say_artifact(
        console, path, f"health at {found.measured_at}: {measured}/{len(KPIS)} KPIs · {len(found.failed)} failed"
    )


async def bench(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    bench: str = "",
    runner: Inject[AssessBench],
    settings: Inject[TaxisSettings],
    console: Inject[Console],
) -> None:
    """Install every arm of the plan fresh in its own fenced sandbox and run it, interleaved; raw samples kept.

    Args:
        nous: the e-nous checkout (its workflow names the step that wrote the plan).
        rundir: the run's folder.
        bench: `false` installs nothing and records the run as not measured; empty = measure.
    """
    plan: Plan = await answer_of(nous, settings, rundir, "Plan")
    found = await runner.run(plan, skip=bench.strip().lower() in SKIP, now=now_utc())
    path = await AssessStore(rundir).put("samples", found)
    runs = sum(len(arm.samples) for arm in found.arms)
    installed = sum(arm.installed for arm in found.arms)
    say_artifact(console, path, found.reason or f"{installed}/{len(found.arms)} arms installed · {runs} samples kept")


async def stats(*, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """The paired bootstrap interval of the difference on the plan's primary metric, against its threshold.

    Args:
        nous: the e-nous checkout (its workflow names the step that wrote the plan).
        rundir: the run's folder.
    """
    store = AssessStore(rundir)
    plan: Plan = await answer_of(nous, settings, rundir, "Plan")
    found = AssessStats().compare(plan, await store.get("samples", Samples))
    path = await store.put("stats", found)
    interval = f" [{found.low:.6g}, {found.high:.6g}]" if found.low is not None and found.high is not None else ""
    say_artifact(
        console, path, f"{found.metric}: {found.outcome}{interval}{f' — {found.reason}' if found.reason else ''}"
    )


async def report(
    *, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Write soa/report.md and soa/assess.json: the verdict as it stood after the adversary; index it for soa-sweep.

    Args:
        nous: the e-nous checkout (its workflow names the steps that answered).
        rundir: the run's folder.
    """
    store, reporter = AssessStore(rundir), AssessReport()
    plan: Plan = await answer_of(nous, settings, rundir, "Plan")
    verdict: Verdict = await answer_of(nous, settings, rundir, "Verdict")
    review: Review = await answer_of(nous, settings, rundir, "Review")
    built = reporter.build(
        await store.get("candidate", Candidate),
        plan=plan,
        health=await store.get("health", Health),
        stats=await store.get("stats", Stats),
        verdict=verdict,
        review=review,
        path=rundir / FOLDER / "report.md",
        date=now_utc().date().isoformat(),
    )
    text = reporter.render(built, plan)
    ### never <rundir>/report.md: the engine writes its own run report there when the run ends.
    await anyio.Path(rundir / FOLDER / "report.md").write_text(text)
    await store.put("assess", built)
    index = await reporter.record(Path(await anyio.Path(settings.taxis_soa_state).expanduser()), built)
    console.out(f"{text}\nindexed: {index}", highlight=False)


async def schemas(
    *, nous: Nous = UNSET, check: bool = False, settings: Inject[TaxisSettings], console: Inject[Console]
) -> None:
    """Write the JSON Schema of every soa-assess port into the workflow's `schemas/`; --check only compares.

    Args:
        nous: the e-nous checkout.
        check: write nothing; fail when a schema differs from its model.
    """
    tree = await GitNous(nous, None).load()
    path = tree.schema["entities"]["workflow"]["path"].replace("{id}", settings.taxis_assess_workflow)
    folder = nous / PurePosixPath(path).parent / SCHEMAS
    found = {
        name: await anyio.Path(folder / f"{name}.json").read_bytes()
        if await anyio.Path(folder / f"{name}.json").is_file()
        else b""
        for name in PORTS
    }
    stale = sorted(name for name, raw in found.items() if raw != schema_text(name))
    match (check, stale):
        case (_, []):
            console.out(f"schemas: {len(PORTS)} in sync in {folder}", highlight=False)
        case (True, _):
            msg = (
                f"stale schemas in {folder}: {', '.join(stale)} — run `taxis workflow soa-assess schemas --nous {nous}`"
            )
            raise AssessError(msg)
        case _:
            await anyio.Path(folder).mkdir(parents=True, exist_ok=True)
            _ = [await anyio.Path(folder / f"{name}.json").write_bytes(schema_text(name)) for name in stale]
            console.out(f"schemas: {len(stale)} written in {folder}", highlight=False)
