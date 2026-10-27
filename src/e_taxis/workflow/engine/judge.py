"""engine.judge: an answer scored against a task's checks, with no model in the loop.

hard = 1 when every check passes, else 0; soft = the fraction that pass. The operators are SkillOpt's (gbrain's
set) plus `not_regex`, which absence of a construct needs. A refusal is a short answer opening with one."""

import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from e_taxis.workflow.models.case import TaskCheck, TaskOp
from e_taxis.workflow.models.metrics import Score

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

##### DEFAULTS #####
REFUSAL: Final[re.Pattern[str]] = re.compile(
    r"^\s*(i can'?t|i cannot|i'?m sorry|sorry,|i am unable|no puedo)", re.IGNORECASE
)
REFUSED: int = 600
### one predicate per operator: (argument, answer) → passed.
OPS: Final[Mapping[TaskOp, Callable[[str, str], bool]]] = MappingProxyType(
    {
        TaskOp.CONTAINS: lambda arg, text: arg.lower() in text.lower(),
        TaskOp.NOT_CONTAINS: lambda arg, text: arg.lower() not in text.lower(),
        TaskOp.REGEX: lambda arg, text: re.search(arg, text) is not None,
        TaskOp.NOT_REGEX: lambda arg, text: re.search(arg, text) is None,
        TaskOp.NO_REFUSAL: lambda _arg, text: not (REFUSAL.search(text) and len(text) < REFUSED),
        TaskOp.MAX_CHARS: lambda arg, text: len(text) <= int(arg),
        TaskOp.MIN_CHARS: lambda arg, text: len(text) >= int(arg),
        TaskOp.SECTION_PRESENT: lambda arg, text: re.search(rf"(?im)^#+\s*{re.escape(arg)}\s*$", text) is not None,
    }
)


##### TYPES #####
class RuleJudge:
    """Deterministic judge over a task's checks."""

    __slots__ = ()

    @staticmethod
    def score(checks: Sequence[TaskCheck], answer: str) -> Score:
        passed = [OPS[check.op](check.arg, answer) for check in checks]
        return Score(hard=float(all(passed)), soft=sum(passed) / len(passed) if passed else 0.0)
