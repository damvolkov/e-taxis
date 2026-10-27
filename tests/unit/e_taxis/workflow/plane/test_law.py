"""tests/unit/e_taxis/workflow/plane/law: one law per target kind — a skill on its render, an agent and a command on
their manifests, a spec by the v2 check — and a plain green for a kind without one."""

from typing import TYPE_CHECKING, Any

from e_taxis.transpile.services.check import CheckService
from e_taxis.workflow.models.metrics import LawMetrics
from e_taxis.workflow.models.plane import Cadence, NodeCard, NodeSpec, Role, Target
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.plane.law import PlaneLaw

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

LAW = NodeSpec(id="law", use="law", card=NodeCard(role=Role.GATE, summary="l"), params={"tree": "base"})


async def test_law_command_reads_the_raw_manifest(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.evaluate(plane_nous, Target.COMMAND, ("ship",), Cadence.COMMIT)
    law = next(run for run in report.runs if run.node == "law")
    assert law.status is Status.FAIL
    assert isinstance(law.metrics, LawMetrics)
    assert "agent 'operator' not in core" in law.metrics.violations


async def test_law_spec_is_the_v2_check(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.evaluate(plane_nous, Target.SPEC, ("claudecode",), Cadence.COMMIT)
    assert next(run for run in report.runs if run.node == "law").status is Status.OK


async def test_law_spec_names_its_blocking_findings(
    plane_nous: Path, plane_state: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    spec = plane_nous / "specs/tekton/claudecode.yaml"
    spec.write_text(spec.read_text() + "\nunknown_top_level: 1\n")
    state = await plane_state(LAW, subjects=("claudecode",), target=Target.SPEC, tree=str(plane_nous))
    outcome = await PlaneLaw(CheckService()).run(plane_context(state, "law", "claudecode"))
    assert outcome.status is Status.FAIL
    assert isinstance(outcome.metrics, LawMetrics)
    assert outcome.metrics.violations[0].startswith("invalid spec")


async def test_law_skill_without_render_skips(
    plane_state: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(LAW)
    outcome = await PlaneLaw(CheckService()).run(plane_context(state, "law"))
    assert (outcome.status, outcome.reason) == (Status.SKIP, "no base render of s1")


async def test_law_kind_without_law_is_green(
    plane_state: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(LAW, target=Target.TOOL)
    outcome = await PlaneLaw(CheckService()).run(plane_context(state, "law"))
    assert outcome.status is Status.OK
    assert outcome.metrics == LawMetrics(tree="base", violations=())
