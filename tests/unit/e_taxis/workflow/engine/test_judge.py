"""tests/unit/e_taxis/workflow/engine/judge: every operator decides on the answer alone; hard is all, soft the share."""

import pytest

from e_taxis.workflow.engine.judge import RuleJudge
from e_taxis.workflow.models.case import TaskCheck, TaskOp
from e_taxis.workflow.models.metrics import Score


@pytest.mark.parametrize(
    ("op", "arg", "answer", "passed"),
    [
        (TaskOp.CONTAINS, "HeapQ", "use heapq", True),
        (TaskOp.NOT_CONTAINS, "sort", "use sorted()", False),
        (TaskOp.REGEX, r"heapq\.nlargest", "heapq.nlargest(3, xs)", True),
        (TaskOp.NOT_REGEX, r"\bfor\b", "for x in xs", False),
        (TaskOp.NO_REFUSAL, "", "I'm sorry, I can't.", False),
        (TaskOp.NO_REFUSAL, "", "Sure: bisect.", True),
        (TaskOp.MAX_CHARS, "5", "123456", False),
        (TaskOp.MIN_CHARS, "3", "1234", True),
        (TaskOp.SECTION_PRESENT, "Plan", "intro\n## Plan\nsteps", True),
    ],
)
async def test_judge_operator(op: TaskOp, arg: str, answer: str, passed: bool) -> None:
    assert RuleJudge.score((TaskCheck(op, arg),), answer).hard == float(passed)


@pytest.mark.parametrize(
    ("checks", "score"),
    [((), Score(1.0, 0.0)), ((TaskCheck(TaskOp.CONTAINS, "a"), TaskCheck(TaskOp.CONTAINS, "z")), Score(0.0, 0.5))],
    ids=["no-checks", "half"],
)
async def test_judge_score(checks: tuple[TaskCheck, ...], score: Score) -> None:
    assert RuleJudge.score(checks, "abc") == score
