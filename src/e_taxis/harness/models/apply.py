"""models.apply: one apply run — the flags that open gates, each step's outcome, each applied part's verify."""

from enum import StrEnum

from msgspec import Struct

from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.verify import VerifyResult


##### ENUMS #####
class ApplyStatus(StrEnum):
    APPLIED = "applied"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    FAILED = "failed"
    NOT_RUN = "not-run"


##### TYPES #####
class ApplyOptions(Struct, frozen=True, kw_only=True):
    """`only` narrows the plan to those ids (empty: all); `licences` and `confirms` open gates by entry id."""

    only: frozenset[str] = frozenset()
    licences: frozenset[str] = frozenset()
    confirms: frozenset[str] = frozenset()


class ApplyStep(Struct, frozen=True, kw_only=True):
    id: str
    status: ApplyStatus
    detail: str


class ApplyReport(Struct, frozen=True, kw_only=True):
    """Steps in install order; `verify` holds one result per applied step."""

    target: Target
    steps: tuple[ApplyStep, ...] = ()
    verify: tuple[VerifyResult, ...] = ()

    @property
    def failed(self) -> tuple[str, ...]:
        return (
            *(step.id for step in self.steps if step.status is ApplyStatus.FAILED),
            *(result.id for result in self.verify if not result.passed),
        )
