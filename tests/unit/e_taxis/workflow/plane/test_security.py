"""tests/unit/e_taxis/workflow/plane/security: the scan of a rendered skill, its findings traced back to core/ (a
SKILL.md line found verbatim in the skill's files, a reference by its own path), accepted ones dropped, the gate red
at the threshold."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from e_taxis.workflow.models.metrics import Finding, SecurityMetrics
from e_taxis.workflow.models.plane import Cadence, NodeCard, NodeSpec, Role, Target
from e_taxis.workflow.models.run import Status
from e_taxis.workflow.plane.security import PlaneSecurity

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_taxis.workflow.services.plane import PlaneRun

SKILL = "algo-py-core"
PLACE = "core/tekton/skills/algo-py-core"
SCAN = NodeSpec(id="security", use="security", card=NodeCard(role=Role.GATE, summary="s"), params={"tree": "base"})


async def test_security_traces_and_accepts(plane_run: PlaneRun, plane_nous: Path, scanner) -> None:
    first = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    flat = (Path(first.folder) / "flat/base/skills/algo-py-core/SKILL.md").read_text().splitlines()
    body = (plane_nous / PLACE / "instructions.md").read_text().splitlines()
    spoken = next(line for line in body if len(line.strip()) > 20)
    rendered = flat.index(spoken) + 1
    scanner.findings = [
        Finding("E1", "HIGH", "SKILL.md", rendered, "curl", "aaaa11112222"),
        Finding("R2", "LOW", "references/lib.md", 3, "x", "bbbb33334444"),
        Finding("F3", "CRITICAL", "SKILL.md", 999, "y", "cccc55556666"),
        Finding("A4", "CRITICAL", "references/lib.md", 1, "z", "dddd77778888"),
    ]
    baseline = plane_nous / "core/tekton/config/security.yaml"
    baseline.write_text(
        "accepted:\n  algo-py-core:\n    - {fingerprint: dddd7777, file: references/lib.md, why: names the threat}\n"
    )
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    (security,) = [run for run in report.runs if run.node == "security"]
    assert security.status is Status.FAIL
    assert isinstance(security.metrics, SecurityMetrics)
    assert [(f.path, f.line) for f in security.metrics.findings] == [
        (f"{PLACE}/instructions.md", body.index(spoken) + 1),
        (f"{PLACE}/references/lib.md", 3),
        ("SKILL.md", 999),
    ]
    assert (security.metrics.accepted, security.metrics.scanner, security.metrics.score) == (1, "fake@v2.12.0", 7)
    assert [need.kind for need in report.needs[SKILL]].count("security") == 3


async def test_security_below_threshold_is_green(plane_run: PlaneRun, plane_nous: Path, scanner) -> None:
    scanner.findings = [Finding("R2", "MEDIUM", "references/lib.md", 3, "x", "bbbb33334444")]
    (plane_nous / "core/tekton/config/security.yaml").unlink()
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    (security,) = [run for run in report.runs if run.node == "security"]
    assert security.status is Status.OK


async def test_security_without_a_pinned_scanner_breaks(plane_run: PlaneRun, plane_nous: Path) -> None:
    (plane_nous / "core/common/stack.yaml").write_text("parts: {}\n")
    report = await plane_run.evaluate(plane_nous, Target.SKILL, (SKILL,), Cadence.COMMIT)
    (security,) = [run for run in report.runs if run.node == "security"]
    assert security.status is Status.ERROR
    assert "no pinned skillspector part" in security.reason


async def test_security_without_render_skips(
    scanner, plane_state: Callable[..., Any], plane_context: Callable[..., Any]
) -> None:
    state = await plane_state(SCAN)
    outcome = await PlaneSecurity(scanner, "HIGH").run(plane_context(state, "security", tree="candidate"))
    assert (outcome.status, outcome.reason) == (Status.SKIP, "no candidate render of s1")
