"""tests/unit/e_taxis/workflow/plane/integrate: the one writer, in its private clone — what it writes in its subject
returns to the sandbox; a write outside it, a new file or the manifest of a skill, or the real checkout refuses it."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.metrics import GradeMetrics, ProposalMetrics
from e_taxis.workflow.models.plane import Cadence, Target
from e_taxis.workflow.models.run import Status

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

SKILL = "algo-py-core"
PLACE = "core/tekton/skills/algo-py-core"
DIRECTIVE = f"Tighten the rule at {PLACE}/instructions.md:3 and keep it short."


async def test_integrate_folds_the_directive_into_the_subject(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    agent.effect = lambda tree: (tree / PLACE / "instructions.md").write_text("# rewritten\n\nOne rule.\n")
    report = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, directive=DIRECTIVE)
    (integrate,) = [run for run in report.runs if run.node == "integrate"]
    assert integrate.status is Status.OK
    assert integrate.metrics == ProposalMetrics(
        proposer="integrator", files=(f"{PLACE}/instructions.md",), lessons=(DIRECTIVE,)
    )
    prompt = agent.calls[0]["prompt"]
    assert f"### {PLACE}/instructions.md:3" in prompt
    assert "Never create a file, never touch skill.yaml." in prompt
    (grade,) = [run for run in report.runs if run.node == "grade"]
    assert isinstance(grade.metrics, GradeMetrics)
    assert grade.metrics.grade == "guidance"
    assert not (plane_nous / PLACE / "instructions.md").read_text().startswith("# rewritten")


@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (
            lambda tree, nous: (tree / "README.md").write_text("x\n"),
            "wrote outside core/tekton/skills/algo-py-core/: README.md",
        ),
        (
            lambda tree, nous: (tree / PLACE / "extra.md").write_text("x\n"),
            "created a file: core/tekton/skills/algo-py-core/extra.md",
        ),
        (
            lambda tree, nous: (tree / PLACE / "skill.yaml").write_text("name: algo-py-core\n"),
            "touched the description's manifest",
        ),
        (lambda tree, nous: (nous / "LEAK.md").write_text("x\n"), "wrote into the real checkout (1 dirty paths)"),
    ],
    ids=["outside", "new-file", "manifest", "real-checkout"],
)
async def test_integrate_refuses(
    plane_run: PlaneRun, plane_nous: Path, agent, effect: Callable[[Path, Path], object], reason: str
) -> None:
    agent.effect = lambda tree: effect(tree, plane_nous)
    report = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, directive=DIRECTIVE)
    (integrate,) = [run for run in report.runs if run.node == "integrate"]
    assert integrate.status is Status.FAIL
    assert reason in integrate.reason
    assert [v.decision.value for v in report.verdicts] == ["settled"]
