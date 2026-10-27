"""tests/unit/e_taxis/workflow/plane/activation: the routing probe over a sandbox around the render — idle where there
is nothing to measure, a case held only when every measured session held it, a transient refusal retried, a quota
or a crash left unmeasured (the node skips: a partial rate is no verdict, nor a break)."""

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.adapters.coder import ClaudeCoder
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.adapters.evals import NousEvals
from e_taxis.workflow.engine.stats import interval_wilson
from e_taxis.workflow.models.metrics import ActivationMetrics, CandidateMetrics, Interval
from e_taxis.workflow.models.plane import NodeSpec
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.plane.activation import PlaneActivation

if TYPE_CHECKING:
    from collections.abc import Callable

SKILL = "algo-py-core"
HITS = "ordeno una lista de tuplas por el segundo campo y me sale O(n²)"
MISS = "monta un makefile con lint y test"
CLAUDE = Path.home() / ".claude"
NODE = NodeSpec(id="activation", use="activation", card=PlaneActivation.card, params={"tree": "base"})


@pytest.mark.parametrize(
    ("upstream", "subject", "tree", "why"),
    [
        ({"intake": Outcome(status=Status.IDLE)}, SKILL, "base", "nothing to enhance: routing not measured"),
        ({"queries": Outcome(status=Status.IDLE)}, SKILL, "base", "no query set"),
        (
            {"candidate": Outcome(status=Status.OK, metrics=CandidateMetrics(out="o", changed=(), fixpoint=True))},
            SKILL,
            "candidate",
            "candidate unchanged: routing is the base's",
        ),
        ({}, "ghost-skill", "base", "no query set"),
    ],
    ids=["nothing-to-enhance", "queries-idle", "unchanged", "no-set"],
)
async def test_activation_idles(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
    coder,
    upstream: dict[str, Outcome],
    subject: str,
    tree: str,
    why: str,
) -> None:
    state = await plane_state(NODE, subjects=(subject,), nous=str(plane_nous))
    _ = [await plane_record(state, node, subject, outcome) for node, outcome in upstream.items()]
    outcome = await plane_nodes["activation"].run(plane_context(state, "activation", subject, tree=tree))
    assert (outcome.status, outcome.reason, coder.probes) == (Status.IDLE, why, [])


async def test_activation_measures_every_case_every_run(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_context: Callable[..., Any],
    coder,
) -> None:
    coder.loads[HITS] = frozenset({SKILL})
    coder.refusals[HITS] = ["claude exited 1: 429 rate limit"]
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    outcome = await plane_nodes["activation"].run(plane_context(state, "activation", SKILL))
    assert (outcome.status, outcome.tokens, outcome.runner) == (Status.OK, 20, "claudecode")
    assert outcome.metrics == ActivationMetrics(
        tree="base",
        mode="activation",
        backend="claudecode",
        passed=2,
        total=2,
        rate=100.0,
        interval=Interval(*(bound * 100 for bound in interval_wilson(4, 4))),
        recall=(1, 1),
        precision=(1, 1),
        unmeasured=0,
    )
    ### one transient refusal, retried: five sessions for four measured runs.
    assert len(coder.probes) == 5
    assert coder.sandboxes == [(state.paths.base, state.paths.node("activation", SKILL) / "home")]


async def test_activation_a_case_that_misfires_fails_its_runs(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_context: Callable[..., Any],
    coder,
) -> None:
    coder.loads[MISS] = frozenset({SKILL})
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    outcome = await plane_nodes["activation"].run(plane_context(state, "activation", SKILL, tree="candidate"))
    assert isinstance(outcome.metrics, ActivationMetrics)
    assert (outcome.metrics.passed, outcome.metrics.recall, outcome.metrics.precision) == (0, (0, 1), (0, 1))
    assert outcome.metrics.failures == (HITS[:80], MISS)
    assert coder.sandboxes[0][0] == state.paths.candidate(SKILL)


@pytest.mark.parametrize(
    ("refusals", "sessions"),
    [(["quota exceeded", "quota exceeded"], 4), (["boom", "boom"], 4), (["429"] * 6, 8)],
    ids=["quota", "crash", "retries-exhausted"],
)
async def test_activation_unanswered_sessions_are_unmeasured(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_context: Callable[..., Any],
    coder,
    refusals: list[str],
    sessions: int,
) -> None:
    coder.refusals[HITS] = refusals
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    outcome = await plane_nodes["activation"].run(plane_context(state, "activation", SKILL))
    assert isinstance(outcome.metrics, ActivationMetrics)
    assert (outcome.status, outcome.reason, outcome.metrics.unmeasured) == (Status.SKIP, "2 sessions unmeasured", 2)
    assert (outcome.metrics.passed, len(coder.probes)) == (1, sessions)


async def test_activation_navigation_reads_the_references(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_context: Callable[..., Any],
    coder,
) -> None:
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    outcome = await plane_nodes["activation"].run(plane_context(state, "activation", SKILL, mode="navigation"))
    assert isinstance(outcome.metrics, ActivationMetrics)
    assert (outcome.metrics.mode, outcome.metrics.recall, outcome.metrics.precision) == ("navigation", (0, 1), (1, 1))
    assert {mode for _, mode in coder.probes} == {"navigation"}


@pytest.mark.slow
@pytest.mark.skipif(
    not (shutil.which("claude") and (CLAUDE / ".credentials.json").is_file()),
    reason="no Claude Code signed in: the real probe needs a model to answer",
)
async def test_activation_real_probe_routes_one_skill(
    plane_state: Callable[..., Any], plane_context: Callable[..., Any], tree, probe_render, probe_nous: Path
) -> None:
    """The real coder on a one-skill render, one session per case: the sorting prompt loads the skill, the Makefile
    one does not. Costs two short sessions."""
    environ = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    node = PlaneActivation(
        NousEvals(), {"claudecode": ClaudeCoder(ShellCommand(environ), CLAUDE)}, runs=1, concurrency=2, limit=180.0
    )
    state = await plane_state(NODE, subjects=("sort-py-keys",), nous=str(probe_nous))
    tree(state.paths.base, probe_render)
    outcome = await node.run(plane_context(state, "activation", "sort-py-keys"))
    assert isinstance(outcome.metrics, ActivationMetrics)
    assert (outcome.status, outcome.metrics.unmeasured, outcome.metrics.passed) == (Status.OK, 0, 2)
    assert outcome.tokens > 0
