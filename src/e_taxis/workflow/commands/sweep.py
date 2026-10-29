"""commands.sweep: `taxis workflow soa-sweep <step>` — soa-sweep's deterministic steps, one command per workflow node.

The workflow (`core/tekton/workflows/soa-sweep/`) calls these as its `run` nodes with `--rundir {{rundir}}` (and
`--nous {{nous}}` where the step reads e-nous); each reads its parents' typed artifacts from `<rundir>/soa/` and
writes its own there — the voices agent reads `soa/entries.json`, report writes `soa/report.md` beside
`soa/report.json` (the run's own `report.md` is the engine's, rewritten when the run ends). The agents' answers (`voices`, `search`) are
read from their `out.md`: which steps answered is the run's own manifest (`run.json`, its agent steps), never an
id written here. `report` is the only step that writes state: the URLs it reported, into the seen ledger."""

import datetime as dt
from collections import Counter
from pathlib import Path, PurePosixPath

import anyio
import msgspec
from rich.console import Console

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.commands.distill import say_artifact
from e_taxis.workflow.distill.store import DistillStore
from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.ports import WebPort
from e_taxis.workflow.models.run import RunManifest, RunPaths
from e_taxis.workflow.models.sweep import PORTS, Entries, Findings, Frame, Report, Seen
from e_taxis.workflow.sweep.deliver import SweepDeliver
from e_taxis.workflow.sweep.fetch import ZONE, SweepFetch
from e_taxis.workflow.sweep.fit import SweepFit
from e_taxis.workflow.sweep.frame import SweepFrame
from e_taxis.workflow.sweep.ground import SweepGround
from e_taxis.workflow.sweep.ledger import SweepLedger
from e_taxis.workflow.sweep.report import SweepReport

##### DEFAULTS #####
WORKFLOW: str = "soa-sweep"
FOLDER: str = "soa"
SCHEMAS: str = "schemas"
LEDGER: str = "ledger.json"
MARKDOWN: str = "report.md"


##### UTILITIES #####
def store_of(rundir: Path) -> DistillStore:
    return DistillStore(rundir, FOLDER)


def markdown_of(rundir: Path) -> Path:
    return rundir / FOLDER / MARKDOWN


def schema_text(name: str) -> bytes:
    """One port's JSON Schema, as the workflow's `schemas/` holds it."""
    return msgspec.json.format(msgspec.json.encode(msgspec.json.schema(PORTS[name])), indent=2) + b"\n"


async def manifest_of(rundir: Path) -> RunManifest:
    """The run's manifest: the checkout it runs in, and its graph."""
    try:
        raw = await anyio.Path(RunPaths(rundir).manifest).read_bytes()
    except FileNotFoundError as missing:
        msg = f"no run.json in {rundir}: this step reads the run's manifest — run it inside `taxis workflow run`"
        raise SweepError(msg) from missing
    return msgspec.json.decode(raw, type=RunManifest)


async def ledger_of(settings: TaxisSettings) -> SweepLedger:
    return SweepLedger(Path(await anyio.Path(settings.taxis_soa_state).expanduser()) / LEDGER)


async def path_of(path: Path) -> Path:
    return Path(await (await anyio.Path(path).expanduser()).resolve())


##### COMMANDS #####
async def frame(
    *,
    nous: Nous = UNSET,
    rundir: Path,
    topic: str = "",
    window: str = "",
    authors: str = "",
    links: str = "",
    console: Inject[Console],
) -> None:
    """Fix the frame from soa.yaml and the run's extras; an unknown topic fails here, at zero tokens.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
        topic: a topic of soa.yaml; empty = the whole plane.
        window: calendar days back from today; empty = soa.yaml's.
        authors: extra voices for this run, space-separated URLs.
        links: extra reference links for this run, space-separated.
    """
    today = dt.datetime.now(ZONE).date()
    fixed = (await SweepFrame.load(nous)).fix(today=today, topic=topic, window=window, authors=authors, links=links)
    path = await store_of(rundir).put("frame", fixed)
    said = f"{fixed.topic or 'the whole plane'}: {len(fixed.keywords)} keywords · {len(fixed.voices)} voices"
    say_artifact(console, path, f"{said} · {len(fixed.links)} links · {fixed.since} → {fixed.until}")


async def ledger(*, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """Read the seen ledger for the frame's voices; nothing is written until report.

    Args:
        rundir: the run's folder.
    """
    store = store_of(rundir)
    seen = await (await ledger_of(settings)).read(await store.get("frame", Frame))
    path = await store.put("seen", seen)
    say_artifact(console, path, f"{sum(len(urls) for urls in seen.seen.values())} URLs seen · {len(seen.seen)} voices")


async def fetch(*, rundir: Path, web: Inject[WebPort], console: Inject[Console]) -> None:
    """Read every voice with its kind's parser and every entry page inside the window.

    Args:
        rundir: the run's folder.
    """
    store = store_of(rundir)
    entries = await SweepFetch(web).fetch(await store.get("frame", Frame), await store.get("seen", Seen))
    rows = [
        f"{voice.id}: {voice.status} · {voice.parsed} parsed · {voice.in_window} in window · {voice.new} new"
        + (f" — {voice.error}" if voice.error else "")
        for voice in entries.voices
    ]
    say_artifact(console, await store.put("entries", entries), "\n".join(rows) or "no voices")


async def ground(*, rundir: Path, web: Inject[WebPort], console: Inject[Console]) -> None:
    """Merge the agents' findings, re-fetch every link, keep what a page holds, rank.

    Args:
        rundir: the run's folder.
    """
    store, manifest = store_of(rundir), await manifest_of(rundir)
    sides = [await store.agent(step.id, Findings) for step in manifest.graph if step.semantic]
    voices = {voice.id for voice in (await store.get("frame", Frame)).voices}
    grounded = await SweepGround(web).ground(sides, voices)
    say_artifact(console, await store.put("grounded", grounded), grounded.notes)


async def fit(*, nous: Nous = UNSET, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """Mark each finding have, considered or new against the corpus, the live trees and past reports.

    Args:
        nous: the e-nous checkout.
        rundir: the run's folder.
    """
    store = store_of(rundir)
    claude = settings.claude_config_dir or Path.home() / ".claude"
    live = [await path_of(claude), await path_of(settings.taxis_workflow_opencode)]
    reports = await path_of(nous / settings.taxis_workflow_reports)
    fitter = await SweepFit.load(await path_of(nous), live, reports, await path_of(rundir))
    fitted = fitter.fit(await store.get("grounded", Findings))
    counts = Counter(str(finding.status) for finding in fitted.findings)
    said = " · ".join(f"{status} {count}" for status, count in counts.items())
    say_artifact(console, await store.put("findings", fitted), said or "no findings")


async def report(*, rundir: Path, settings: Inject[TaxisSettings], console: Inject[Console]) -> None:
    """Write soa/report.md and soa/report.json; record the reported URLs in the seen ledger.

    Args:
        rundir: the run's folder.
    """
    store, reporter = store_of(rundir), SweepReport()
    framed, entries = await store.get("frame", Frame), await store.get("entries", Entries)
    fitted = await store.get("findings", Findings)
    markdown = markdown_of(rundir)
    built = reporter.build(entries, fitted, str(markdown))
    await store.put("report", built)
    text = reporter.render(framed, built, fitted.notes)
    await anyio.Path(markdown).write_text(text)
    added = await (await ledger_of(settings)).record(reporter.seen(framed, entries, built))
    console.out(text, highlight=False)
    console.out(f"ledger: {added} URLs recorded · {len(built.assess)} to assess", highlight=False)


async def deliver(*, rundir: Path, web: Inject[WebPort], console: Inject[Console]) -> None:
    """Post the report's summary to the Discord webhook soa.yaml names, soa/report.md attached.

    Args:
        rundir: the run's folder.
    """
    store, nous = store_of(rundir), Path((await manifest_of(rundir)).nous)
    config = (await SweepFrame.load(nous)).config
    summary = await SweepDeliver(web).deliver(
        webhook=config.discord.webhook,
        base=nous,
        frame=await store.get("frame", Frame),
        report=await store.get("report", Report),
        markdown=await anyio.Path(markdown_of(rundir)).read_text(),
    )
    console.out(summary, highlight=False)


async def schemas(*, nous: Nous = UNSET, check: bool = False, console: Inject[Console]) -> None:
    """Write the JSON Schema of every soa-sweep port into the workflow's `schemas/`; --check only compares.

    Args:
        nous: the e-nous checkout.
        check: write nothing; fail when a schema differs from its model.
    """
    tree = await GitNous(nous, None).load()
    path = tree.schema["entities"]["workflow"]["path"].replace("{id}", WORKFLOW)
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
                f"stale schemas in {folder}: {', '.join(stale)} — run `taxis workflow soa-sweep schemas --nous {nous}`"
            )
            raise SweepError(msg)
        case _:
            await anyio.Path(folder).mkdir(parents=True, exist_ok=True)
            _ = [await anyio.Path(folder / f"{name}.json").write_bytes(schema_text(name)) for name in stale]
            console.out(f"schemas: {len(stale)} written in {folder}", highlight=False)
