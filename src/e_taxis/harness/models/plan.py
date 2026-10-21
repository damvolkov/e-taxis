"""models.plan: the resolver's join and the planner's verdict — read-only, nothing here has been applied."""

from enum import StrEnum

from msgspec import Struct

from e_taxis.harness.models.catalog import CatalogEntry, Target
from e_taxis.harness.models.wanted import WantedPart


##### ENUMS #####
class PlanAction(StrEnum):
    """What apply would do with a part — or why it cannot."""

    SKIP = "skip"
    INSTALL = "install"
    UPDATE = "update"
    DEFERRED = "deferred"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


##### TYPES #####
class Resolved(Struct, frozen=True, kw_only=True):
    """A wanted part joined to its catalog entry, at its place in the install order."""

    entry: CatalogEntry
    wanted: WantedPart
    order: int


class Resolution(Struct, frozen=True, kw_only=True):
    """The join for one target: resolved parts in install order, and the wanted ids no entry knows."""

    resolved: tuple[Resolved, ...] = ()
    unknown: tuple[WantedPart, ...] = ()


class Probe(Struct, frozen=True, kw_only=True):
    """One shell probe: exit 0 means present; `version` is the first line it printed, if any."""

    present: bool
    version: str | None
    detail: str


class PlanStep(Struct, frozen=True, kw_only=True):
    """`held` is the install or update a blocked step holds back until its gate opens."""

    id: str
    action: PlanAction
    reason: str
    held: PlanAction | None = None


class Plan(Struct, frozen=True, kw_only=True):
    """Every step for one target, in install order; unknown parts last."""

    target: Target
    steps: tuple[PlanStep, ...] = ()

    @property
    def failed(self) -> tuple[PlanStep, ...]:
        return tuple(step for step in self.steps if step.action in {PlanAction.UNKNOWN, PlanAction.BLOCKED})
