"""tests/e2e/plane: the evaluator against the real e-nous checkout — read-only, slow, never in CI.

`taxis eval run skill data-py-cache --cadence commit` runs its deterministic nodes green (law, the ledgers read where
they live, security when SkillSpector is installed), the run written under tmp; and every file of a real v2 render
reads back through its format unchanged (the candidate's fixpoint holds on the whole corpus). No agent runs; nothing
is written to the checkout."""

import os
import shutil
from pathlib import Path

import pytest

from e_taxis.transpile.engine.encode import match_target
from e_taxis.transpile.engine.reverse import classify_reverse
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.workflow.adapters.coder import ClaudeCoder, OpencodeCoder
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.adapters.evals import NousEvals
from e_taxis.workflow.adapters.ledger import JsonlLedger
from e_taxis.workflow.adapters.lock import FlockLock
from e_taxis.workflow.adapters.provider import HouseProvider
from e_taxis.workflow.adapters.runner import AnthropicRunner
from e_taxis.workflow.adapters.sandbox import GitSandbox
from e_taxis.workflow.adapters.scanner import SkillspectorScanner
from e_taxis.workflow.models.plane import Cadence, Target
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.plane.activation import PlaneActivation
from e_taxis.workflow.plane.effect import PlaneEffect
from e_taxis.workflow.plane.law import PlaneLaw
from e_taxis.workflow.plane.needs import PlaneNeeds
from e_taxis.workflow.plane.queries import PlaneQueries
from e_taxis.workflow.plane.render import PlaneRender
from e_taxis.workflow.plane.security import PlaneSecurity
from e_taxis.workflow.plane.semantic import PlaneSemantic
from e_taxis.workflow.plane.snapshot import PlaneSnapshot
from e_taxis.workflow.plane.tasks import PlaneTasks
from e_taxis.workflow.services.plane import PlaneRun

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not (Path("~/workspaces/damien/e-nous").expanduser() / "core").is_dir(), reason="no e-nous"),
]

##### DEFAULTS #####
NOUS = Path("~/workspaces/damien/e-nous").expanduser()
SKILL = "data-py-cache"
CLAUDE = Path.home() / ".claude"


@pytest.mark.skipif(not shutil.which("uvx"), reason="no uvx: SkillSpector cannot run")
@pytest.mark.timeout(600)
async def test_plane_evaluates_a_real_skill_read_only(tmp_path: Path) -> None:
    command = ShellCommand(os.environ)
    sandbox, checker, evals = GitSandbox(command), CheckService(), NousEvals()
    nodes = {
        "snapshot": PlaneSnapshot(command, sandbox),
        "render": PlaneRender(RunService(checker), Path.home()),
        "law": PlaneLaw(checker),
        "security": PlaneSecurity(SkillspectorScanner(command, 300.0), "HIGH"),
        "queries": PlaneQueries(evals),
        "tasks": PlaneTasks(evals),
        ### the weekly measures idle at the commit cadence: wired, never paid for here.
        "semantic": PlaneSemantic(SkillspectorScanner(command, 300.0), "HIGH", HouseProvider(os.environ), "builder"),
        "activation": PlaneActivation(
            evals,
            {"opencode": OpencodeCoder(command, Path.home() / ".config"), "claudecode": ClaudeCoder(command, CLAUDE)},
            runs=1,
            concurrency=1,
            limit=60.0,
        ),
        "effect": PlaneEffect(
            evals,
            HouseProvider(os.environ),
            AnthropicRunner(tokens=64, limit=60.0),
            tier="scout",
            seeds=1,
            split="test",
            concurrency=1,
        ),
        "needs": PlaneNeeds(),
    }
    runner = PlaneRun(
        nodes,
        sandbox,
        FlockLock(wait=5.0),
        JsonlLedger.open,
        concurrency=4,
        reports=tmp_path / "reports",
        backend="opencode",
    )
    before = await sandbox.fingerprint(NOUS)
    report = await runner.evaluate(NOUS, Target.SKILL, (SKILL,), Cadence.COMMIT)
    statuses = {run.node: run.status for run in report.runs}
    assert {statuses[node] for node in ("snapshot", "render", "law", "security", "queries", "needs")} == {Status.OK}
    assert {statuses[node] for node in ("semantic", "activation", "effect")} == {Status.IDLE}
    assert report.folder.startswith(str(tmp_path))
    assert await sandbox.fingerprint(NOUS) == before


async def test_plane_real_render_reads_back_unchanged(tmp_path: Path) -> None:
    render = PlaneRender(RunService(CheckService()), Path.home())
    tree, projection = await render.project(NOUS, "opencode", tmp_path / "flat")
    spec = RunService.spec(tree, "opencode")
    unread = [
        path
        for path, placements in projection.placements.items()
        if path in projection.files
        and any(
            classify_reverse(
                spec,
                path,
                match_target(path, spec["targets"]),
                placements,
                live=(tmp_path / "flat" / path).read_bytes(),
                base=None,
            )
        )
    ]
    assert unread == []
