"""tests/unit/e_taxis/services/plan: probe every resolved part and decide — skip, install, update, blocked, unknown."""

from typing import TYPE_CHECKING

from e_taxis.models.catalog import Target
from e_taxis.models.plan import PlanAction

if TYPE_CHECKING:
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
