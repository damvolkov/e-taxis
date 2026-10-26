"""tests/unit/e_taxis/workflow/commands/distill: `taxis distill <step>` through the real app, step after step.

Defect 1: grade read the answers of `nodes/mine-arkhetypo` while the workflow's node is `mine-blueprint`. Which steps
answered is now read from the workflow's own output ports — here the miners are `mine-harness` and `mine-blueprint`
only because their ports write `Mining`. Defect 2: scan's changed files are the run's committed range, whatever the
code graph says about the working tree."""

import json
import shutil
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.distill import (
    Candidate,
    Deltas,
    Grade,
    HarnessPart,
    HarnessTarget,
    Indexes,
    Inventory,
    Judgement,
    Manifest,
    Mining,
    Relation,
    Report,
    Review,
    Verdict,
)
from e_taxis.workflow.models.entity import Entity

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_resources import Resources

type Taxis = Callable[..., tuple[int, str, str]]
SCALING = HarnessTarget(entity=Entity.SKILL, id="sys-gen-scaling", part=HarnessPart.LIB)
EVENTS = HarnessTarget(entity=Entity.SKILL, id="arch-py-events", part=HarnessPart.INSTRUCTIONS)


@pytest.fixture
def distill_env(monkeypatch: pytest.MonkeyPatch, resources: Resources, tmp_path: Path) -> Path:
    """The code graph is the stand-in script; the blueprint a checkout under tmp, read at `main`."""
    graph = tmp_path / "graph"
    shutil.copy(resources.path / "workflow" / "graph", graph)
    graph.chmod(0o755)
    monkeypatch.setenv("TAXIS_DISTILL_GRAPH", str(graph))
    monkeypatch.setenv("TAXIS_DISTILL_BLUEPRINT", str(tmp_path / "e-arkhetypo"))
    monkeypatch.setenv("TAXIS_DISTILL_REF", "main")
    monkeypatch.setenv("TAXIS_DISTILL_CACHE", str(tmp_path / "cache"))
    return graph


def read(rundir: Path, name: str, kind: Any) -> Any:
    return msgspec.json.decode((rundir / "distill" / f"{name}.json").read_bytes(), type=kind)


def test_distill_front_steps_read_the_committed_range(
    taxis: Taxis, distill_env: Path, repo: Path, rundir: Path, harness: Path, cores: tuple[Path, Path, Path, str]
) -> None:
    run = ("--rundir", str(rundir))
    code, out, _ = taxis("distill", "guard", *run, "--project", str(repo), "--since", "main", "--work", "x faster")
    assert code == 0
    assert f"artifact: {rundir}/distill/scope.json" in out
    assert taxis("distill", "intake", *run)[0] == 0
    assert read(rundir, "manifest", Manifest).commits[0].subject == "docs: notes"
    code, out, _ = taxis("distill", "scan", *run)
    deltas = read(rundir, "deltas", Deltas)
    assert code == 0
    assert deltas.changed == ("a.py", "conf.yaml", "docs/notes.md", "logo.png")
    assert [s.file for s in deltas.impacted] == ["a.py"]
    assert "4 files changed · 1 symbols impacted" in out
    code, out, _ = taxis("distill", "drift", *run)
    assert (code, "no drift checks in this project" in out) == (0, True)
    code, out, _ = taxis("distill", "index", "--nous", str(harness), *run)
    assert code == 0
    assert read(rundir, "indexes", Indexes).project.endswith("-proj")


def test_distill_guard_nothing_exits_three(taxis: Taxis, repo: Path, rundir: Path) -> None:
    code, _, err = taxis("distill", "guard", "--rundir", str(rundir), "--project", str(repo), "--since", "feat/x")
    assert code == 3
    assert "no commit past" in err


def test_distill_inventory_writes_the_facts(
    taxis: Taxis, distill_env: Path, cores: tuple[Path, Path, Path, str], rundir: Path
) -> None:
    _, harness, project, _ = cores
    run = ("--rundir", str(rundir))
    assert taxis("distill", "guard", *run, "--project", str(project))[0] == 0
    assert taxis("distill", "intake", *run)[0] == 0
    code, out, _ = taxis("distill", "inventory", "--nous", str(harness), *run)
    assert code == 0
    assert "behind its blueprint" in out
    assert read(rundir, "inventory", Inventory).facts


def test_distill_grade_report_ship_along_the_workflow_ports(
    taxis: Taxis,
    distill_env: Path,
    harness: Path,
    rundir: Path,
    repo: Path,
    answer: Callable[[str, Any], None],
    candidate: Callable[..., Candidate],
    resources: Resources,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cores: tuple[Path, Path, Path, str],
) -> None:
    (harness / "core" / "versioning").mkdir(parents=True)
    shutil.copy(resources.path / "workflow" / "matrix.yaml", harness / "core" / "versioning" / "matrix.yaml")
    run = ("--rundir", str(rundir))
    assert taxis("distill", "guard", *run, "--project", str(repo), "--since", "main")[0] == 0
    contradiction = candidate("c1", SCALING, relation=Relation.CONTRADICTS, replaces=("awa",))
    answer("mine-harness", Mining(candidates=(contradiction,)))
    answer("mine-blueprint", Mining(candidates=(candidate("c2", EVENTS),)))
    code, out, _ = taxis("distill", "grade", "--nous", str(harness), *run)
    grades = read(rundir, "grades", tuple[Grade, ...])
    assert code == 0
    assert [g.candidate for g in grades] == ["c1", "c2"]
    assert "core/tekton/skills/test-py-tdd/references/lib.md" in grades[0].propagated
    assert json.loads(out.splitlines()[0])[0]["candidate"] == "c1"
    (rundir / "distill" / "indexes.json").write_bytes(
        msgspec.json.encode(Indexes(harness="h", blueprint="b", project="p", heads={"h": "abc1234"}))
    )
    (rundir / "distill" / "inventory.json").write_bytes(msgspec.json.encode(Inventory(facts=())))
    answer("worth", (Judgement(candidate="c1", verdict=Verdict.MUST, generality=0.9, rationale="lies"),))
    answer("audit2", (Review(candidate="c1", upheld=True),))
    code, out, _ = taxis("distill", "report", "--nous", str(harness), *run)
    assert code == 0
    assert "# reverse-distill · proj" in out
    assert (rundir / "briefs" / "c1.md").read_text().startswith("sketch c1")
    assert read(rundir, "report", Report).proposals[0].review == Review(candidate="c1", upheld=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "taxis").write_text('#!/bin/sh\necho ran "$@"\n')
    (bin_dir / "taxis").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    code, out, _ = taxis("distill", "ship", "--nous", str(harness), *run)
    assert code == 0
    assert "ran workflow run emaintenance --nous" in out
    assert "shipped 1 must(s)" in out


def test_distill_report_without_a_review_still_reports(
    taxis: Taxis, distill_env: Path, nous: Path, rundir: Path, repo: Path, answer: Callable[[str, Any], None]
) -> None:
    run = ("--rundir", str(rundir))
    assert taxis("distill", "guard", *run, "--project", str(repo), "--since", "main")[0] == 0
    store = rundir / "distill"
    store.joinpath("indexes.json").write_bytes(msgspec.json.encode(Indexes(harness="h", blueprint="b", project="p")))
    store.joinpath("inventory.json").write_bytes(msgspec.json.encode(Inventory(facts=())))
    _ = [store.joinpath(f"{name}.json").write_bytes(b"[]") for name in ("candidates", "grades", "waivers")]
    answer("worth", ())
    code, out, _ = taxis("distill", "report", "--nous", str(nous), *run)
    assert code == 0
    assert "**0 proposals**" in out


def test_distill_grade_needs_a_workflow_that_names_its_miners(
    taxis: Taxis, nous: Path, rundir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAXIS_DISTILL_WORKFLOW", "demo")
    code, _, err = taxis("distill", "grade", "--nous", str(nous), "--rundir", str(rundir))
    assert code == 25
    assert "demo: no step writes a Mining" in err


def test_distill_schemas_write_then_check(taxis: Taxis, nous: Path) -> None:
    folder = nous / "core" / "tekton" / "workflows" / "reverse-distill" / "schemas"
    code, _, err = taxis("distill", "schemas", "--nous", str(nous), "--check")
    assert code == 25
    assert "stale schemas" in err
    code, out, _ = taxis("distill", "schemas", "--nous", str(nous))
    assert (code, "14 written" in out) == (0, True)
    assert "replaces" in (folder / "Candidates.json").read_text()
    code, out, _ = taxis("distill", "schemas", "--nous", str(nous), "--check")
    assert (code, "14 in sync" in out) == (0, True)
