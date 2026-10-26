"""models.report: what a transpiler run found — one finding per divergence, each pointing at its source.

A finding names its backend (or `core`), where it sits in the spec (`config[3]`, `persona`) or the core
(`agent/builder`), the path it is about and why. The stamp versions the run: the checkout, the commit read,
the model and every spec's version. Kinds are a subset of `specs/base.yaml · report.kinds`; only `signal` is
informational, every other kind blocks."""

from enum import StrEnum

from msgspec import Struct

##### DEFAULTS #####
CORE: str = "core"


##### ENUMS #####
class ReportKind(StrEnum):
    INVALID = "invalid"
    ORPHAN = "orphan"
    UNCOVERED = "uncovered"
    UNDECLARED = "undeclared"
    UNUSED = "unused"
    BLOCK = "block"
    INVERTIBLE = "invertible"
    PRESENCE = "presence"
    SIGNAL = "signal"
    MISSING = "missing"
    DRIFT = "drift"
    STALE = "stale"
    SYMLINK = "symlink"
    HARNESS = "harness"

    @property
    def blocking(self) -> bool:
        return self is not ReportKind.SIGNAL


##### TYPES #####
class ReportFinding(Struct, frozen=True, kw_only=True):
    kind: ReportKind
    backend: str
    where: str
    path: str
    detail: str = ""
    sources: tuple[str, ...] = ()


class ReportStamp(Struct, frozen=True, kw_only=True):
    """`specs` is backend → the model version its file declares."""

    root: str
    commit: str
    model: str
    specs: dict[str, str]


class Report(Struct, frozen=True, kw_only=True):
    stamp: ReportStamp
    findings: tuple[ReportFinding, ...] = ()

    @property
    def blocking(self) -> tuple[ReportFinding, ...]:
        return tuple(finding for finding in self.findings if finding.kind.blocking)
