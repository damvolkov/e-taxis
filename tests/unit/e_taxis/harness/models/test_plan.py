"""tests/unit/e_taxis/models/plan: a plan fails on what it cannot do — unknown or blocked — never on work to do."""

from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.plan import Plan, PlanAction, PlanStep


def test_plan_failed_holds_unknown_and_blocked_only() -> None:
    steps = tuple(PlanStep(id=action.value, action=action, reason="") for action in PlanAction)
    failed = Plan(target=Target.CLAUDECODE, steps=steps).failed
    assert {step.action for step in failed} == {PlanAction.UNKNOWN, PlanAction.BLOCKED}
    assert PlanAction.DEFERRED not in {step.action for step in failed}
