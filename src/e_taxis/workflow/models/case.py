"""models.case: the evaluator's two ledgers — routing queries and effect tasks — as typed cases, and their law.

Both are brain data in the e-nous checkout, one Markdown per skill whose first fenced `toml` block is the machine's:
`[[case]]` for a query set (does the description win the routing decision it should), `[[task]]` for a task set
(does the body make an agent answer better). The two are different questions with different owners, so they never
share a file. Validation is zero tokens: a query set cites only skills and references that exist; a task set has
unique ids, every split populated, judges that are outcomes and regexes that compile.

A query case is measured in one of three modes, each asking the same question of different fields: `activation`
(which skills load: `expect`/`reject`), `navigation` (which references open: `reads`/`skips`), `preload` (whether the
answer was already in the baseline: `markers` recited, `not_loaded` never loaded). The fields are the dispatch: a
frozen table per side, never a branch."""

import re
from collections import Counter
from collections.abc import Callable, Mapping
from enum import StrEnum, auto
from operator import attrgetter
from types import MappingProxyType
from typing import Final

from msgspec import Struct


##### TYPES #####
class ProbeMode(StrEnum):
    """What a routing probe measures: which skill loads, which reference opens, or that nothing needed loading."""

    ACTIVATION = auto()
    NAVIGATION = auto()
    PRELOAD = auto()


class ProbeResult(Struct, frozen=True):
    """What one probe session did: loaded, opened, answered — or `error`, when no answer came back at all."""

    loaded: frozenset[str] = frozenset()
    opened: frozenset[str] = frozenset()
    text: str = ""
    tokens: int = 0
    error: str | None = None

    @property
    def measured(self) -> bool:
        """An unanswered run is neither pass nor fail: folding it in would read an API error as an under-trigger."""
        return self.error is None


def recited_case(marker: str, text: str) -> bool:
    """A marker survives any dressing the answer gives it: both sides stripped to lowercase alphanumerics."""
    return "".join(filter(str.isalnum, marker.lower())) in "".join(filter(str.isalnum, text.lower()))


##### DEFAULTS #####
WANTED: Final[Mapping[ProbeMode, Callable[[QueryCase], frozenset[str]]]] = MappingProxyType(
    {
        ProbeMode.ACTIVATION: attrgetter("expect"),
        ProbeMode.NAVIGATION: attrgetter("reads"),
        ProbeMode.PRELOAD: attrgetter("markers"),
    }
)
AVOIDED: Final[Mapping[ProbeMode, Callable[[QueryCase], frozenset[str]]]] = MappingProxyType(
    {
        ProbeMode.ACTIVATION: attrgetter("reject"),
        ProbeMode.NAVIGATION: attrgetter("skips"),
        ProbeMode.PRELOAD: attrgetter("not_loaded"),
    }
)
### a preload marker lives in the answer text, not in an event: what was observed is the loads plus the markers recited.
OBSERVED: Final[Mapping[ProbeMode, Callable[[QueryCase, ProbeResult], frozenset[str]]]] = MappingProxyType(
    {
        ProbeMode.ACTIVATION: lambda _case, result: result.loaded,
        ProbeMode.NAVIGATION: lambda _case, result: result.opened,
        ProbeMode.PRELOAD: lambda case, result: (
            result.loaded | frozenset(m for m in case.markers if recited_case(m, result.text))
        ),
    }
)


##### TYPES #####
class QueryCase(Struct, frozen=True, kw_only=True):
    """A realistic prompt and what must, and must not, follow from it. `owner` names who should win a negative."""

    prompt: str
    expect: frozenset[str] = frozenset()
    reject: frozenset[str] = frozenset()
    reads: frozenset[str] = frozenset()
    skips: frozenset[str] = frozenset()
    owner: frozenset[str] = frozenset()
    markers: frozenset[str] = frozenset()
    not_loaded: frozenset[str] = frozenset()

    @property
    def cited(self) -> frozenset[str]:
        """Every skill the case names."""
        return self.expect | self.reject | self.owner | self.not_loaded

    def qualified(self, skill: str) -> frozenset[str]:
        """Every reference the case names, as `<skill>/<file>`: a bare name belongs to the set's own skill."""
        return frozenset(ref if "/" in ref else f"{skill}/{ref}" for ref in self.reads | self.skips)

    def positive(self, mode: ProbeMode) -> bool:
        """Whether the case asserts something must happen, rather than must not."""
        return bool(WANTED[mode](self))

    def asserts(self, mode: ProbeMode) -> bool:
        """Whether the case says anything at all in this mode: a silent case would only add free passes."""
        return bool(WANTED[mode](self) or AVOIDED[mode](self))

    def holds(self, mode: ProbeMode, result: ProbeResult) -> bool:
        """Everything wanted happened and nothing avoided did."""
        got = OBSERVED[mode](self, result)
        return not ((WANTED[mode](self) - got) or (AVOIDED[mode](self) & got))


class TaskSplit(StrEnum):
    """Where a task may be used: a proposer trains and gates on train and val; the verdict reads test."""

    TRAIN = auto()
    VAL = auto()
    TEST = auto()


class TaskOp(StrEnum):
    """Judge operators — the set SkillOpt scores with."""

    CONTAINS = auto()
    NOT_CONTAINS = auto()
    REGEX = auto()
    NOT_REGEX = auto()
    NO_REFUSAL = auto()
    MAX_CHARS = auto()
    MIN_CHARS = auto()
    SECTION_PRESENT = auto()

    @property
    def shape(self) -> bool:
        """Formatting-only: satisfiable without the answer improving."""
        return self in {TaskOp.MAX_CHARS, TaskOp.MIN_CHARS, TaskOp.SECTION_PRESENT}

    @property
    def pattern(self) -> bool:
        return self in {TaskOp.REGEX, TaskOp.NOT_REGEX}


class TaskCheck(Struct, frozen=True):
    """One judge condition over an answer."""

    op: TaskOp
    arg: str = ""

    @property
    def compiles(self) -> bool:
        try:
            re.compile(self.arg)
        except re.error:
            return False
        return True


class TaskCase(Struct, frozen=True, kw_only=True):
    """One task: the prompt, its split, every check its answer must pass."""

    id: str
    split: TaskSplit
    prompt: str
    checks: tuple[TaskCheck, ...]

    @property
    def problems(self) -> tuple[str, ...]:
        shape = bool(self.checks) and all(check.op.shape for check in self.checks)
        return (
            *((f"{self.id}: no checks",) if not self.checks else ()),
            *((f"{self.id}: shape-only judge — won by reformatting",) if shape else ()),
            *(
                f"{self.id}: bad regex {check.arg!r}"
                for check in self.checks
                if check.op.pattern and not check.compiles
            ),
        )


class QuerySet(Struct, frozen=True, kw_only=True):
    """One skill's routing ledger."""

    skill: str
    cases: tuple[QueryCase, ...]

    def problems(self, skills: frozenset[str], references: frozenset[str]) -> tuple[str, ...]:
        """Every way the set cites a corpus that does not hold it: `skills` the ids, `references` `<skill>/<file>`."""
        cited = frozenset().union(*(case.cited for case in self.cases))
        named = frozenset().union(*(case.qualified(self.skill) for case in self.cases))
        return (
            *(f"unknown skill cited: {name}" for name in sorted(cited - skills)),
            *(f"unknown reference: {ref}" for ref in sorted(named - references)),
        )


class TaskSet(Struct, frozen=True, kw_only=True):
    """One skill's effect ledger."""

    skill: str
    tasks: tuple[TaskCase, ...]

    @property
    def splits(self) -> dict[str, int]:
        return dict(Counter(task.split.value for task in self.tasks))

    @property
    def problems(self) -> tuple[str, ...]:
        """Every way the set could make an effect verdict meaningless."""
        ids = Counter(task.id for task in self.tasks)
        return (
            *(f"duplicate task id {ident}" for ident, seen in ids.items() if seen > 1),
            *(problem for task in self.tasks for problem in task.problems),
            *(f"no {split} tasks" for split in TaskSplit if self.tasks and split.value not in self.splits),
        )
