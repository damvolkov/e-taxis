"""tests/unit/e_taxis/services/plan: probe every resolved part and decide — skip, install, update, blocked, unknown."""

from typing import TYPE_CHECKING

from e_taxis.models.catalog import Target
from e_taxis.models.plan import PlanAction

if TYPE_CHECKING:
    from e_taxis.services.apply import ApplyService
    from e_taxis.services.plan import PlanService


async def test_plan_run_profile(planner: PlanService, house) -> None:
    plan = await planner.run(house, Target.CLAUDECODE)
    assert [(step.id, step.action) for step in plan.steps] == [
        ("alpha", PlanAction.SKIP),
        ("delta", PlanAction.BLOCKED),
        ("beta", PlanAction.INSTALL),
        ("ghost", PlanAction.UNKNOWN),
    ]
    assert "Elastic-2.0" in plan.steps[1].reason


async def test_plan_run_engineer_compares_the_pin(planner: PlanService, engineer) -> None:
    plan = await planner.run(engineer, Target.CLAUDECODE)
    assert [(step.id, step.action, step.reason) for step in plan.steps[:2]] == [
        ("alpha", PlanAction.SKIP, "present · 1.2.3 matches pin v1.2.3"),
        ("epsilon", PlanAction.UPDATE, "found 1.2.3, pin 9.9"),
    ]


async def test_plan_run_defers_what_p3_writes_and_holds_the_gated_action(applier: ApplyService, profile) -> None:
    plan = await applier.plan(profile("house"), Target.CLAUDECODE, frozenset())
    steps = {step.id: step for step in plan.steps}
    assert (steps["svc"].action, steps["svc"].reason) == (PlanAction.DEFERRED, "deferred: compose lands in P3")
    assert (steps["gated"].action, steps["gated"].held) == (PlanAction.BLOCKED, PlanAction.INSTALL)
    assert (steps["here"].action, steps["tool"].action) == (PlanAction.SKIP, PlanAction.INSTALL)
