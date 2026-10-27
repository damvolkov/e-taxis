"""tests/unit/e_taxis/workflow/services/plane: evaluations and enhancements end to end on a real mini e-nous checkout.

Only the scanner, the agent and the trial are fakes; git, the v2 render and the ledger are real. Defect 7 of the legacy
`emaintenance`: `evaluate` ran after a skipped `promote` and measured the unpromoted checkout. An evaluation asked for
an enhancer run's candidate now measures that candidate — its base with its patches — promoted or not."""

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import IdleError, PlaneError, ReasonError
from e_taxis.workflow.models.metrics import LawMetrics, NeedsMetrics, Owner
from e_taxis.workflow.models.plane import Cadence, Plane, Target
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.models.verdict import Decision

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from e_taxis.workflow.models.report import PlaneReport
    from e_taxis.workflow.services.plane import PlaneRun

SKILL = "algo-py-core"
DESCRIPTION = "core/tekton/skills/algo-py-core/skill.yaml"
LONG = "description: " + "x" * 230 + ". Use when long.\n"


def statuses(report: PlaneReport, subject: str = SKILL) -> dict[str, Status]:
    return {run.node: run.status for run in report.runs if run.subject in {subject, ""}}


async def test_plane_evaluate_measures_the_checkout(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    assert statuses(report) == {
        "snapshot": Status.OK,
        "render": Status.OK,
        "law": Status.OK,
        "security": Status.OK,
        "queries": Status.FAIL,
        "tasks": Status.OK,
        "semantic": Status.IDLE,
        "activation": Status.IDLE,
        "effect": Status.IDLE,
        "needs": Status.OK,
    }
    assert report.manifest.tree == str(plane_nous)
    assert [need.kind for need in report.needs[SKILL]] == ["coverage", "coverage"]
    assert (Path(report.folder) / "report.md").read_text() == report.markdown
    assert not (Path(report.folder) / "sandbox").exists()


async def test_plane_evaluate_weekly_measures_the_heuristics(
    plane_run: PlaneRun, plane_nous: Path, scanner, echo
) -> None:
    """W2 had dropped `semantic`, `activation` and `effect`: at the weekly cadence they run — the scan's LLM stage on
    the semantic tier, the A/B on the render — and routing waits on a valid query set."""
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.WEEKLY)
    found = statuses(report)
    assert (found["semantic"], found["activation"], found["effect"]) == (Status.OK, Status.SKIP, Status.OK)
    assert {llm.model if llm else None for llm in scanner.llms} == {None, "builder"}
    assert len(echo.systems) == 4


async def test_plane_evaluate_only_runs_the_named_measures(
    plane_run: PlaneRun, plane_nous: Path, scanner, echo
) -> None:
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.WEEKLY, only=("semantic",))
    found = statuses(report)
    assert (found["semantic"], found["activation"], found["effect"], found["law"]) == (
        Status.OK,
        Status.IDLE,
        Status.IDLE,
        Status.OK,
    )
    assert echo.systems == []


async def test_plane_evaluate_refuses_an_unknown_measure(plane_run: PlaneRun, plane_nous: Path) -> None:
    with pytest.raises(PlaneError, match="--only names no measure of skill: law"):
        await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.WEEKLY, only=("law",))


async def test_plane_evaluate_refuses_an_unknown_subject(plane_run: PlaneRun, plane_nous: Path) -> None:
    with pytest.raises(PlaneError, match="unknown subject"):
        await plane_run.evaluate(plane_nous, Target.SKILL, ("nope",), Cadence.COMMIT)


@pytest.mark.parametrize(
    ("source", "directive", "manual", "ids", "message"),
    [
        ("", "", False, (SKILL,), "needs a reason"),
        ("", "do it", False, (), "names the subjects"),
    ],
    ids=["no-reason", "directive-without-ids"],
)
async def test_plane_enhance_refuses(
    plane_run: PlaneRun, plane_nous: Path, source: str, directive: str, manual: bool, ids: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ReasonError, match=message):
        await plane_run.enhance(
            plane_nous, Target.SKILL, ids, Cadence.COMMIT, source=source, directive=directive, manual=manual
        )


async def test_plane_enhance_refuses_dirty_subject_without_manual(plane_run: PlaneRun, plane_nous: Path) -> None:
    (plane_nous / DESCRIPTION).write_text((plane_nous / DESCRIPTION).read_text() + "# touched\n")
    with pytest.raises(ReasonError, match="uncommitted edits in algo-py-core"):
        await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, directive="tighten")


async def test_plane_enhance_from_a_clean_evaluation_is_idle(plane_run: PlaneRun, plane_nous: Path) -> None:
    await plane_run.evaluate(plane_nous, Target.AGENT, (), Cadence.COMMIT)
    with pytest.raises(IdleError, match="states no need"):
        await plane_run.enhance(plane_nous, Target.AGENT, (), Cadence.COMMIT, source="latest", owner=Owner.HUMAN)


async def test_plane_enhance_manual_edit_is_graded_decided_and_patched(plane_run: PlaneRun, plane_nous: Path) -> None:
    lib = plane_nous / "core/tekton/skills/algo-py-core/references/lib.md"
    lib.write_text(lib.read_text() + "\nOne more line of depth.\n")
    report = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, manual=True)
    (verdict,) = report.verdicts
    ### an idle gate (here the integrator, with no lesson) caps the verdict at propose, as in v1.
    assert verdict.decision is Decision.PROPOSE
    assert verdict.grade == "deepening"
    assert "grade deepening ≤ ceiling deepening" in verdict.reasons
    assert Path(verdict.patch).read_text().count("+One more line of depth.") == 1
    assert statuses(report)["integrate"] is Status.IDLE
    assert not (Path(report.folder) / "trees").exists()


async def test_plane_enhance_without_change_settles(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, manual=True)
    assert [v.decision for v in report.verdicts] == [Decision.SETTLED]


async def test_plane_enhance_from_evaluation_acts_on_agent_needs(plane_run: PlaneRun, plane_nous: Path, agent) -> None:
    evaluation = await plane_run.evaluate(plane_nous, Target.AGENT, (), Cadence.COMMIT)
    report = await plane_run.enhance(
        plane_nous, Target.AGENT, (), Cadence.COMMIT, source=evaluation.manifest.run_id, owner=Owner.AGENT
    )
    assert report.manifest.subjects == ("builder",)
    assert report.manifest.source == evaluation.manifest.run_id
    assert agent.calls[0]["agent"] == "integrator"
    assert "Fix the house law" in agent.calls[0]["prompt"]
    assert [v.decision for v in report.verdicts] == [Decision.SETTLED]


async def test_plane_evaluate_candidate_measures_the_unpromoted_change(
    plane_run: PlaneRun, plane_nous: Path, git: Callable[..., Awaitable[str]]
) -> None:
    manifest = plane_nous / DESCRIPTION
    manifest.write_text(re.sub(r"description: >-\n(  .*\n)+", LONG, manifest.read_text()))
    enhanced = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, manual=True)
    await git(plane_nous, "checkout", "-q", "--", "core")
    assert [v.decision for v in enhanced.verdicts] == [Decision.REJECT]
    checkout = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    candidate = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, candidate="latest")
    assert candidate.manifest.candidate == enhanced.manifest.run_id
    assert candidate.manifest.patched == ()
    (law,) = [run for run in candidate.runs if run.node == "law"]
    assert law.status is Status.OK
    assert checkout.manifest.candidate == ""


async def test_plane_evaluate_candidate_applies_the_patch_promote_skipped(
    plane_run: PlaneRun, plane_nous: Path, git: Callable[..., Awaitable[str]]
) -> None:
    lib = plane_nous / "core/tekton/skills/algo-py-core/references/lib.md"
    lib.write_text(lib.read_text() + "\nPatched depth.\n")
    enhanced = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, manual=True)
    await git(plane_nous, "checkout", "-q", "--", "core")
    report = await plane_run.evaluate(
        plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, candidate=enhanced.manifest.run_id, keep=True
    )
    measured = Path(report.manifest.tree) / "core/tekton/skills/algo-py-core/references/lib.md"
    assert report.manifest.patched == (SKILL,)
    assert measured.read_text().endswith("Patched depth.\n")
    assert not lib.read_text().endswith("Patched depth.\n")
    rendered = Path(report.folder) / "flat/base/skills/algo-py-core/references/lib.md"
    assert rendered.read_text().endswith("Patched depth.\n")


async def test_plane_evaluate_candidate_refuses_a_patch_that_does_not_apply(
    plane_run: PlaneRun, plane_nous: Path
) -> None:
    lib = plane_nous / "core/tekton/skills/algo-py-core/references/lib.md"
    lib.write_text(lib.read_text() + "\nPatched depth.\n")
    enhanced = await plane_run.enhance(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, manual=True)
    (verdict,) = enhanced.verdicts
    Path(verdict.patch).write_text("not a patch\n")
    with pytest.raises(PlaneError, match="does not apply to its own base"):
        await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT, candidate="latest")


async def test_plane_folder_resolves_ids_and_latest(plane_run: PlaneRun, plane_nous: Path) -> None:
    first = await plane_run.evaluate(plane_nous, Target.AGENT, (), Cadence.COMMIT)
    assert (await plane_run.folder(plane_nous, first.manifest.run_id)).name == first.manifest.run_id
    assert (await plane_run.folder(plane_nous, "latest", Plane.EVALUATOR, Target.AGENT)).name == first.manifest.run_id
    with pytest.raises(PlaneError, match="no enhancer"):
        await plane_run.folder(plane_nous, "latest", Plane.ENHANCER)
    with pytest.raises(PlaneError, match="'nope'"):
        await plane_run.folder(plane_nous, "nope")


async def test_plane_load_rebuilds_the_report(plane_run: PlaneRun, plane_nous: Path) -> None:
    report = await plane_run.evaluate(plane_nous, Target.AGENT, (), Cadence.COMMIT)
    loaded = await plane_run.load(Path(report.folder))
    assert loaded.markdown == report.markdown
    (needs,) = [run for run in loaded.runs if run.node == "needs"]
    assert isinstance(needs.metrics, NeedsMetrics)
    (law,) = [run for run in loaded.runs if run.node == "law"]
    assert isinstance(law.metrics, LawMetrics)


async def test_plane_describe_names_every_graph(plane_run: PlaneRun) -> None:
    described = plane_run.describe(Plane.ENHANCER)
    assert "## enhancer/skill" in described
    assert "## enhancer/spec" in described
    assert "speckeeper" in described
