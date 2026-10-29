"""tests/unit/e_taxis/workflow/commands/sweep: `taxis workflow radar-field <step>` through the real app, step after step,
the web recorded, the ledger and the live trees under tmp."""

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.graph import GraphSpec, StepSpec
from e_taxis.workflow.models.run import RunManifest
from e_taxis.workflow.models.sweep import (
    Entries,
    Findings,
    FindingStatus,
    Frame,
    Report,
    Seen,
    Voice,
    VoiceKind,
    VoiceStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.sweep import Finding

type Taxis = Callable[..., tuple[int, str, str]]
POST = "https://www.linkedin.com/posts/adavoice_tracing-otel-activity-1111111111111111111-AbCd"
REPO = "https://github.com/spanline/spanline"
FRAME = Frame(
    brief="b",
    topic="observability",
    keywords=("agent tracing",),
    since="2026-10-26",
    until="2026-10-28",
    voices=(
        Voice(id="ada", url="https://www.linkedin.com/in/adavoice", kind=VoiceKind.LINKEDIN_PROFILE),
        Voice(id="down", url="https://down.example/feed", kind=VoiceKind.ATOM_FEED),
    ),
)


@pytest.fixture
def sweep_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tree) -> Path:
    """The ledger's state under tmp (one URL already seen), empty live trees: the state folder."""
    state = tmp_path / "state"
    tree(state, {"ledger.json": msgspec.json.encode(Seen(seen={"ada": {POST: "2026-10-01"}})).decode()})
    monkeypatch.setenv("TAXIS_RADAR_STATE", str(state))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("TAXIS_WORKFLOW_OPENCODE", str(tmp_path / "opencode"))
    return state


@pytest.fixture
def put(rundir: Path) -> Callable[[str, Any], None]:
    """An artifact a parent step left in `<rundir>/radar/`."""

    def write(name: str, value: Any) -> None:
        (rundir / "radar").mkdir(parents=True, exist_ok=True)
        (rundir / "radar" / f"{name}.json").write_bytes(msgspec.json.encode(value))

    return write


@pytest.fixture
def manifest(rundir: Path, radar_nous: Path) -> RunManifest:
    """The run.json `taxis workflow run` writes: radar-field's graph, its two agent steps among the commands."""
    steps = tuple(
        StepSpec(id=ident, run="" if ident in {"voices", "search"} else f"taxis workflow radar-field {ident}")
        for ident in ("frame", "ledger", "fetch", "voices", "search", "ground", "fit", "report", "deliver")
    )
    run = RunManifest(
        run_id="r1",
        workflow="radar-field",
        nous=str(radar_nous),
        base_sha="0" * 40,
        started=dt.datetime(2026, 10, 28, tzinfo=dt.UTC),
        graph=GraphSpec(summary="radar-field", steps=steps),
    )
    rundir.mkdir(parents=True, exist_ok=True)
    (rundir / "run.json").write_bytes(msgspec.json.encode(run))
    return run


def read(rundir: Path, name: str, kind: Any) -> Any:
    return msgspec.json.decode((rundir / "radar" / f"{name}.json").read_bytes(), type=kind)


def test_sweep_frame_writes_the_frame(taxis: Taxis, radar_nous: Path, rundir: Path) -> None:
    run = ("--nous", str(radar_nous), "--rundir", str(rundir))
    code, out, _ = taxis(
        "workflow", "radar-field", "frame", *run, "--topic", "observability", "--window", "", "--authors", ""
    )
    framed = read(rundir, "frame", Frame)
    assert code == 0
    assert f"artifact: {rundir}/radar/frame.json" in out
    assert "observability: 2 keywords · 1 voices · 2 links" in out
    assert dt.date.fromisoformat(framed.until) - dt.date.fromisoformat(framed.since) == dt.timedelta(days=2)


def test_sweep_frame_unknown_topic_fails(taxis: Taxis, radar_nous: Path, rundir: Path) -> None:
    code, _, err = taxis(
        "workflow", "radar-field", "frame", "--nous", str(radar_nous), "--rundir", str(rundir), "--topic", "x"
    )
    assert code == 25
    assert "unknown topic 'x'" in err


def test_sweep_ledger_then_fetch(taxis: Taxis, web_deps, sweep_env: Path, rundir: Path, put) -> None:
    put("frame", FRAME)
    code, out, _ = taxis("workflow", "radar-field", "ledger", "--rundir", str(rundir))
    assert (code, "1 URLs seen · 1 voices" in out) == (0, True)
    code, out, _ = taxis("workflow", "radar-field", "fetch", "--rundir", str(rundir))
    entries = read(rundir, "entries", Entries)
    assert code == 0
    assert "ada: ok · 3 parsed · 2 in window · 1 new" in out
    assert "down: error · 0 parsed · 0 in window · 0 new — https://down.example/feed: 404 Not Found" in out
    assert [voice.status for voice in entries.voices] == [VoiceStatus.OK, VoiceStatus.ERROR]


def test_sweep_ground_fit_report_deliver(
    taxis: Taxis,
    web_deps,
    sweep_env: Path,
    rundir: Path,
    radar_nous: Path,
    manifest: RunManifest,
    put,
    answer: Callable[[str, Any], None],
    finding: Callable[..., Finding],
    tree,
) -> None:
    put("frame", FRAME)
    put("entries", Entries(voices=()))
    answer("voices", Findings(findings=(finding("Spanline", via="ada", relevance=5),)))
    answer("search", Findings(findings=(finding("Ghost", links=("https://gone.example",)),)))
    code, out, _ = taxis("workflow", "radar-field", "ground", "--rundir", str(rundir))
    assert (code, "ground: 1 of 2 kept · Ghost: no link answered" in out) == (0, True)
    code, out, _ = taxis("workflow", "radar-field", "fit", "--nous", str(radar_nous), "--rundir", str(rundir))
    assert (code, "new 1" in out) == (0, True)
    code, out, _ = taxis("workflow", "radar-field", "report", "--rundir", str(rundir))
    built = read(rundir, "report", Report)
    assert code == 0
    assert built.assess == (f"taxis workflow run radar-tech tech={REPO}",)
    assert built.findings[0].status is FindingStatus.NEW
    assert (rundir / "radar" / "report.md").read_text().startswith("# radar-field — observability")
    assert built.path == str(rundir / "radar" / "report.md")
    assert not (rundir / "report.md").exists()
    assert "ledger: 1 URLs recorded · 1 to assess" in out
    assert REPO in json.loads((sweep_env / "ledger.json").read_text())["seen"]["ada"]
    radar = radar_nous / "core" / "tekton" / "config" / "radar.yaml"
    radar.write_text(radar.read_text().replace('webhook: ""', "webhook: hook"))
    tree(radar_nous, {"hook": "https://discord.com/api/webhooks/1/x"})
    code, out, _ = taxis("workflow", "radar-field", "deliver", "--rundir", str(rundir))
    assert (code, out.startswith("**radar-field** · observability")) == (0, True)
    url, _, files = web_deps.posted[0]
    assert url == "https://discord.com/api/webhooks/1/x"
    assert files["files[0]"][1] == (rundir / "radar" / "report.md").read_bytes()


def test_sweep_ground_refuses_a_malformed_answer(
    taxis: Taxis, web_deps, rundir: Path, manifest: RunManifest, put, answer: Callable[[str, Any], None]
) -> None:
    put("frame", FRAME)
    answer("voices", {"findings": [{"title": "only a title"}]})
    answer("search", Findings(findings=()))
    code, _, err = taxis("workflow", "radar-field", "ground", "--rundir", str(rundir))
    assert code == 25
    assert "step voices's answer does not fit Findings" in err


def test_sweep_ground_without_a_manifest(taxis: Taxis, web_deps, rundir: Path) -> None:
    code, _, err = taxis("workflow", "radar-field", "ground", "--rundir", str(rundir))
    assert code == 25
    assert "no run.json" in err


def test_sweep_deliver_without_a_webhook(taxis: Taxis, web_deps, rundir: Path, manifest: RunManifest, put) -> None:
    put("frame", FRAME)
    put("report", Report(path="", voices=(), findings=(), assess=()))
    (rundir / "radar" / "report.md").write_text("# R\n")
    code, _, err = taxis("workflow", "radar-field", "deliver", "--rundir", str(rundir))
    assert code == 25
    assert "names no webhook file" in err


def test_sweep_schemas_write_then_check(taxis: Taxis, nous: Path) -> None:
    folder = nous / "core" / "tekton" / "workflows" / "radar-field" / "schemas"
    code, _, err = taxis("workflow", "radar-field", "schemas", "--nous", str(nous), "--check")
    assert code == 25
    assert "stale schemas" in err
    code, out, _ = taxis("workflow", "radar-field", "schemas", "--nous", str(nous))
    assert (code, "5 written" in out) == (0, True)
    assert "the voice id it came through" in (folder / "Findings.json").read_text()
    code, out, _ = taxis("workflow", "radar-field", "schemas", "--nous", str(nous), "--check")
    assert (code, "5 in sync" in out) == (0, True)
