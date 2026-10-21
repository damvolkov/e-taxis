"""models.uninstall: one uninstall run — the part and, with --cascade, its dependents first; each step's outcome."""

from enum import StrEnum

from msgspec import Struct

from e_taxis.harness.models.catalog import Target


##### ENUMS #####
class UninstallStatus(StrEnum):
    REMOVED = "removed"
    PLANNED = "planned"
    ABSENT = "absent"
    DEFERRED = "deferred"
    FAILED = "failed"
    NOT_RUN = "not-run"


##### TYPES #####
class UninstallStep(Struct, frozen=True, kw_only=True):
    id: str
    status: UninstallStatus
    detail: str


class UninstallReport(Struct, frozen=True, kw_only=True):
    target: Target
    steps: tuple[UninstallStep, ...] = ()

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(step.id for step in self.steps if step.status is UninstallStatus.FAILED)
