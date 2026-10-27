"""tests/unit/e_taxis/workflow/plane/effect: the paired A/B — idle without a change or a held-out task, `value` against
no skill, `delta` against the candidate, the whole skill as the context and every score kept beside the node."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.metrics import CandidateMetrics, EffectMetrics, Interval, Score
from e_taxis.workflow.models.plane import NodeSpec
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.plane.effect import PlaneEffect

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SKILL = "algo-py-core"
NODE = NodeSpec(id="effect", use="effect", card=PlaneEffect.card, params={"mode": "delta"})
ROUTER = "# algo\nuse bisect\n"


@pytest.mark.parametrize(
    ("changed", "subject", "why"),
    [((), SKILL, "candidate unchanged"), (("x",), "ghost-skill", "no test tasks")],
    ids=["unchanged", "no-tasks"],
)
async def test_effect_idles(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
    echo,
    changed: tuple[str, ...],
    subject: str,
    why: str,
) -> None:
    state = await plane_state(NODE, subjects=(subject,), nous=str(plane_nous))
    candidate = CandidateMetrics(out="o", changed=changed, fixpoint=True)
    await plane_record(state, "candidate", subject, Outcome(status=Status.OK, metrics=candidate))
    outcome = await plane_nodes["effect"].run(plane_context(state, "effect", subject))
    assert (outcome.status, outcome.reason, echo.systems) == (Status.IDLE, why, [])


async def test_effect_value_measures_the_skill_against_none(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_context: Callable[..., Any],
    tree,
    echo,
    provider,
) -> None:
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    tree(state.paths.base / "skills" / SKILL, {"SKILL.md": ROUTER, "references/b.md": "B", "references/a.md": "A"})
    outcome = await plane_nodes["effect"].run(plane_context(state, "effect", SKILL, mode="value"))
    context = "<!-- SKILL.md -->\n# algo\nuse bisect\n\n\n<!-- references/a.md -->\nA\n\n<!-- references/b.md -->\nB"
    assert sorted(echo.systems) == ["", "", context, context]
    assert (outcome.status, outcome.tokens, outcome.runner, provider.tiers) == (Status.OK, 8, "anthropic", ["scout"])
    assert outcome.metrics == EffectMetrics(
        split="test",
        tasks=1,
        seeds=2,
        base=Score(1.0, 1.0),
        candidate=Score(1.0, 1.0),
        delta=Score(0.0, 0.0),
        hard=Interval(0.0, 0.0),
        soft=Interval(0.0, 0.0),
        per_task={"t3": (1.0, 1.0)},
        mode="value",
    )
    kept = msgspec.json.decode((state.paths.node("effect", SKILL) / "outcomes.json").read_bytes())
    assert (outcome.artifacts, kept["tasks"], len(kept["base"][0])) == (
        (str(state.paths.node("effect", SKILL) / "outcomes.json"),),
        ["t3"],
        2,
    )


async def test_effect_delta_measures_the_candidate(
    plane_nodes: dict[str, Any],
    plane_nous: Path,
    plane_state: Callable[..., Any],
    plane_record: Callable[..., Any],
    plane_context: Callable[..., Any],
    tree,
    echo,
) -> None:
    state = await plane_state(NODE, subjects=(SKILL,), nous=str(plane_nous))
    tree(state.paths.base / "skills" / SKILL, {"SKILL.md": "base"})
    tree(state.paths.candidate(SKILL) / "skills" / SKILL, {"SKILL.md": "candidate"})
    changed = CandidateMetrics(out="o", changed=("SKILL.md",), fixpoint=True)
    await plane_record(state, "candidate", SKILL, Outcome(status=Status.OK, metrics=changed))
    outcome = await plane_nodes["effect"].run(plane_context(state, "effect", SKILL))
    assert isinstance(outcome.metrics, EffectMetrics)
    assert (outcome.metrics.mode, outcome.metrics.delta) == ("delta", Score(0.0, 0.0))
    assert sorted(echo.systems) == ["<!-- SKILL.md -->\nbase"] * 2 + ["<!-- SKILL.md -->\ncandidate"] * 2
