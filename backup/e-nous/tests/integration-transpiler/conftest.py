"""The transpiler trial as a graph of session fixtures: each node one fixture, its struct reported, its dependents its inputs.

    sandbox ─▶ applied ─▶ placement
                  └────▶ sight ─▶ remembered ─▶ plan ─▶ absorbed ─▶ settled ─▶ resight ─▶ outcomes

A node that fails errors every node after it — the graph's own semantics, for free. The
nodes are `ops.trial` classes; these fixtures only wire them to one recipe's sandbox and
write what each returned. `op` runs from the sandbox's copy, under the fence, as a human
would run it: apply, absorb, apply again, plan.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.trial import Judgement, Memory, Placement, Plan, Recipe, Run, Settle, Sight
from ops.transpiler.render import Transpiler
from ops.trial.command import FencedCommand
from ops.trial.fence import LandrunFence
from ops.trial.ghost import SpecGhost
from ops.trial.memory import PipelineMemory
from ops.trial.mutation import HarnessMutation
from ops.trial.placement import TreePlacement
from ops.trial.report import TrialReport
from ops.trial.sandbox import RecipeSandbox
from ops.trial.settle import PlanSettle
from tests.integration.capture import HttpCapture


@pytest.fixture(scope="session")
def sandbox(recipe: Recipe, root: Path, capture: HttpCapture) -> RecipeSandbox:
    return RecipeSandbox(recipe, root / str(recipe), settings.ROOT, os.environ["PATH"], capture.url).build()


@pytest.fixture(scope="session")
def command(fence: LandrunFence, sandbox: RecipeSandbox) -> FencedCommand:
    return FencedCommand(fence, [sandbox.root])


@pytest.fixture(scope="session")
def op(command: FencedCommand, sandbox: RecipeSandbox) -> Callable[..., Awaitable[Run]]:
    """`op <args>` from the sandbox's copy, fenced, with the sandbox's settings."""

    async def run(*args: str) -> Run:
        argv = [sys.executable, "-m", "ops.cli.main", *args]
        return await command.run(argv, sandbox.ops, sandbox.repo, 600.0)

    return run


@pytest.fixture(scope="session")
def ghost(sandbox: RecipeSandbox, command: FencedCommand, capture: HttpCapture) -> SpecGhost:
    return SpecGhost(sandbox, command, capture)


# ------------------------------------------------------------------- nodes
@pytest.fixture(scope="session")
async def applied(op: Callable[..., Awaitable[Run]], sandbox: RecipeSandbox, report: TrialReport) -> Run:
    """core/ → the harness tree: `op transpiler apply`, then the topology's links."""
    run = await op("transpiler", "apply", *sandbox.targets, "--yes")
    sandbox.link(tuple(doc.target for doc in sandbox.render().documents))
    report.write(str(sandbox.recipe), "1-apply", run)
    return run


@pytest.fixture(scope="session")
def render(applied: Run, sandbox: RecipeSandbox) -> Transpiler:
    """The render the first apply wrote: the ground truth every later node is measured against."""
    return sandbox.render()


@pytest.fixture(scope="session")
async def placement(
    render: Transpiler, op: Callable[..., Awaitable[Run]], sandbox: RecipeSandbox, report: TrialReport
) -> Placement:
    """The transpiler's replication gate, run where the apply ran: nothing missing, nothing drifted, links whole."""
    gate = await op("transpiler", "check", *sandbox.targets)
    found = TreePlacement(gate, len(render.files), sandbox.linked).check()
    report.write(str(sandbox.recipe), "2-placement", found)
    return found


@pytest.fixture(scope="session")
async def sight(placement: Placement, ghost: SpecGhost, render: Transpiler, report: TrialReport) -> Sight:
    """The phantom raised over the applied tree: what it loaded."""
    found, shown = await ghost.load(render)
    report.sight(str(ghost.sandbox.recipe), "3-load", found, shown)
    return found


@pytest.fixture(scope="session")
async def remembered(
    sight: Sight, sandbox: RecipeSandbox, command: FencedCommand, capture: HttpCapture, report: TrialReport
) -> Memory | None:
    """The phantom's memory fed over the applied tree, before any mutation touches it; None when the spec declares none."""
    found = await PipelineMemory(sandbox, command, capture).run()
    report.write(str(sandbox.recipe), "3-memory", found)
    return found


@pytest.fixture(scope="session")
def plan(
    sight: Sight,
    remembered: Memory | None,
    render: Transpiler,
    seed: int,
    sandbox: RecipeSandbox,
    report: TrialReport,
) -> Plan:
    """The seeded mutations, drawn from the spec and written into the live tree."""
    mutation = HarnessMutation(render, seed)
    drawn = mutation.plan()
    mutation.apply(drawn)
    report.write(str(sandbox.recipe), "4-mutate", drawn)
    return drawn


@pytest.fixture(scope="session")
async def absorbed(plan: Plan, op: Callable[..., Awaitable[Run]], sandbox: RecipeSandbox, report: TrialReport) -> Run:
    """The harness folded back: `op transpiler absorb`."""
    run = await op("transpiler", "absorb", "--backend", sandbox.recipe.backend.value, "--yes")
    report.write(str(sandbox.recipe), "5-absorb", run)
    return run


@pytest.fixture(scope="session")
async def settled(
    absorbed: Run, op: Callable[..., Awaitable[Run]], sandbox: RecipeSandbox, report: TrialReport
) -> Settle:
    """core/ applied again, then planned: after absorb and apply, nothing may be left to move."""
    again = await op("transpiler", "apply", *sandbox.targets, "--yes")
    planned = await op("transpiler", "plan", *sandbox.targets, "--render", "json")
    found = PlanSettle(again, planned).check()
    report.write(str(sandbox.recipe), "6-settle", found)
    return found


@pytest.fixture(scope="session")
async def resight(settled: Settle, ghost: SpecGhost, sandbox: RecipeSandbox, report: TrialReport) -> tuple[Sight, str]:
    """The phantom raised again over the settled tree, against the render of the absorbed core."""
    found, shown = await ghost.load(sandbox.render())
    report.sight(str(sandbox.recipe), "7-reload", found, shown)
    return found, "\n".join(shown.values())


@pytest.fixture(scope="session")
def outcomes(resight: tuple[Sight, str], plan: Plan, sandbox: RecipeSandbox, report: TrialReport) -> Judgement:
    """Every mutation judged: in core after absorb, in the harness after the reload."""
    render = sandbox.render()
    found = HarnessMutation(render, plan.seed).judge(
        plan, sandbox.repo / "core", resight[1], frozenset(sandbox.recipe.ghost.blind)
    )
    report.write(str(sandbox.recipe), "8-outcomes", found)
    return found
