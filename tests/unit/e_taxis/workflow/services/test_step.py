"""tests/unit/e_taxis/workflow/services/step: one step — a real bash command, a fake agent, a loop check, an idle copy."""

from typing import TYPE_CHECKING, Any

from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.metrics import LoopMetrics, LoopState, SessionMetrics
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from e_taxis.workflow.models.ports import NodeContext, RunState
    from e_taxis.workflow.services.step import WorkflowStep

type Contexts = Callable[[RunState, str], NodeContext]
type Record = Callable[..., Awaitable[None]]


async def test_step_command_binds_the_run_and_hands_down_the_lock(
    step: WorkflowStep, state: Callable[..., Any], context: Contexts, tmp_path: Path
) -> None:
    spec = StepSpec(id="a", run="printf '%s|%s|%s|%s' {{run}} \"{{value}}\" '{{nous}}' \"$TAXIS_LOCK\"")
    (tmp_path / "n o").mkdir()
    run = await state(spec, params={"value": 'he said "$(no)"'}, nous=str(tmp_path / "n o"))
    outcome = await step.run(context(run, "a"))
    said = run.paths.out("a").read_text()
    assert outcome.status is Status.OK
    assert said == f'r1|he said "$(no)"|{tmp_path / "n o"}|token'
    assert outcome.metrics == SessionMetrics(agent="run", narrative=(said,))


async def test_step_command_exit_three_is_a_skip(
    step: WorkflowStep, state: Callable[..., Any], context: Contexts
) -> None:
    run = await state(StepSpec(id="a", run="echo nothing to distill; exit 3"))
    outcome = await step.run(context(run, "a"))
    assert (outcome.status, outcome.runner) == (Status.SKIP, "bash")
    assert "exited 3" in outcome.reason


async def test_step_command_failure_is_a_fail_with_its_last_line(
    step: WorkflowStep, state: Callable[..., Any], context: Contexts
) -> None:
    run = await state(StepSpec(id="a", run="echo first; echo the real reason >&2; exit 2"))
    outcome = await step.run(context(run, "a"))
    assert outcome.status is Status.FAIL
    assert "the real reason" in outcome.reason


async def test_step_not_due_is_idle(step: WorkflowStep, state: Callable[..., Any], context: Contexts) -> None:
    run = await state(StepSpec(id="a", run="exit 9", when={"apply": ("true",)}), params={"apply": ""})
    outcome = await step.run(context(run, "a"))
    assert (outcome.status, outcome.reason) == (Status.IDLE, "not when apply=true")


async def test_step_agent_is_told_the_run_so_far(
    step: WorkflowStep, agent, state: Callable[..., Any], context: Contexts, record: Record
) -> None:
    graph = (
        StepSpec(id="a", run="echo said by a"),
        StepSpec(id="b", run="x"),
        StepSpec(id="c", depends=("a", "b"), run="x"),
        StepSpec(id="d", depends=("c",), actor="builder", instruction="look at {{rundir}}", readonly=True, steps=3),
    )
    run = await state(*graph)
    await step.run(context(run, "a"))
    await record(run, "b", Outcome(status=Status.SKIP, reason="why"))
    outcome = await step.run(context(run, "d"))
    call = agent.calls[0]
    assert (outcome.status, outcome.tokens, outcome.cached, outcome.runner) == (Status.OK, 7, 3, "opencode")
    assert (call["agent"], call["readonly"], call["steps"]) == ("builder", True, 3)
    assert call["prompt"].startswith(f"look at {run.paths.root}")
    assert "### a\nsaid by a" in call["prompt"]
    assert "### b\nskip: why" in call["prompt"]
    assert "### c\nnever ran" in call["prompt"]


async def test_step_lead_drives_the_orchestrator(
    step: WorkflowStep, agent, state: Callable[..., Any], context: Contexts
) -> None:
    run = await state(StepSpec(id="a", instruction="report"))
    outcome = await step.run(context(run, "a"))
    assert agent.calls[0]["agent"] == "orchestrator"
    assert outcome.metrics == SessionMetrics(agent="orchestrator", narrative=("the agent's answer",))


async def test_step_refused_agent_fails_the_step(
    step: WorkflowStep, agent, state: Callable[..., Any], context: Contexts
) -> None:
    agent.failing.add("builder")
    run = await state(StepSpec(id="a", actor="builder", instruction="i"))
    outcome = await step.run(context(run, "a"))
    assert (outcome.status, outcome.reason) == (Status.FAIL, "agent 'builder' refused")


async def test_step_until_closes_stalls_and_stays_open(
    step: WorkflowStep, state: Callable[..., Any], context: Contexts, record: Record, tmp_path: Path
) -> None:
    flag = tmp_path / "closed"
    check = f"test -f {flag} || {{ echo still open; exit 1; }}"
    graph = (
        StepSpec(id="check_1", run=check, until=True, iteration=1),
        StepSpec(id="check_2", run=check, until=True, iteration=2, previous="check_1"),
        StepSpec(id="check_3", run=check, until=True, iteration=3, previous="check_2"),
    )
    run = await state(*graph)
    first = await step.run(context(run, "check_1"))
    await record(run, "check_1", first)
    second = await step.run(context(run, "check_2"))
    flag.touch()
    third = await step.run(context(run, "check_3"))
    assert [o.metrics.state for o in (first, second, third) if isinstance(o.metrics, LoopMetrics)] == [
        LoopState.OPEN,
        LoopState.STALLED,
        LoopState.CLOSED,
    ]
    assert first.metrics == LoopMetrics(
        iteration=1, state=LoopState.OPEN, open=1, digest=getattr(first.metrics, "digest", "")
    )


async def test_step_until_broken_check_fails(step: WorkflowStep, state: Callable[..., Any], context: Contexts) -> None:
    run = await state(StepSpec(id="check_1", run="exit 4", until=True, iteration=1))
    outcome = await step.run(context(run, "check_1"))
    assert outcome.status is Status.FAIL


async def test_step_copy_after_an_ending_check_is_idle(
    step: WorkflowStep, state: Callable[..., Any], context: Contexts, record: Record
) -> None:
    graph = (
        StepSpec(id="check_1", run="true", until=True, iteration=1),
        StepSpec(id="work_2", run="exit 9", iteration=2, closers=("check_1",)),
    )
    run = await state(*graph)
    await record(run, "check_1", await step.run(context(run, "check_1")))
    outcome = await step.run(context(run, "work_2"))
    assert (outcome.status, outcome.reason) == (Status.IDLE, "loop ended at check_1")
