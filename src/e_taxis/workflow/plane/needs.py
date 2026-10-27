"""plane.needs: the evaluator's conclusion for one subject — every reason to act on it, as typed needs.

A pure function over the subject's ledger rows: no model, no judgment. What the enhancer may act on is exactly this
list, plus a directive of yours.

| kind | comes from | read as |
|---|---|---|
| `law` | a law's violations | the entity breaks the house law |
| `security` | an unaccepted scanner finding | the text may instruct harm, or the scanner could not read it |
| `coverage` | a missing or invalid query / task set | routing or effect cannot be measured |
| `drift` | an upstream signal of a backend's sources | a spec lags its harness |
| `broken` | a node that failed or broke without a reading | the entity does not render or load |"""

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final

from e_taxis.workflow.models.metrics import (
    LawMetrics,
    LedgerMetrics,
    Need,
    NeedsMetrics,
    SecurityMetrics,
    SignalMetrics,
)
from e_taxis.workflow.models.plane import Guard, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.ports import PlaneContext

##### DEFAULTS #####
NODE: str = "needs"
### ledger gaps that leave a skill unmeasurable: an idle row with this reason is a coverage need.
UNCOVERED: Final[frozenset[str]] = frozenset({"no query set", "no task set"})
### drift in these categories is context the maintainer reads, never a reason to act.
CONTEXT: Final[frozenset[str]] = frozenset({"core", "community"})


##### UTILITIES #####
def needs_law(run: NodeRun, metrics: LawMetrics) -> list[Need]:
    return [Need("law", run.node, violation) for violation in metrics.violations]


def needs_security(run: NodeRun, metrics: SecurityMetrics) -> list[Need]:
    return [
        Need("security", run.node, f"[{f.fingerprint[:12]}] {f.rule} {f.severity} {f.path}:{f.line} {f.detail}")
        for f in metrics.findings
    ]


def needs_ledger(run: NodeRun, metrics: LedgerMetrics) -> list[Need]:
    return [Need("coverage", run.node, f"{metrics.kind}: {problem}") for problem in metrics.problems]


def needs_signals(run: NodeRun, metrics: SignalMetrics) -> list[Need]:
    return [
        Need("drift", run.node, f"{s.category}/{s.source}: {s.detail}")
        for s in metrics.signals
        if s.category not in CONTEXT
    ]


### how each kind of evidence reads as needs; kinds absent here carry none.
READERS: Final[Mapping[type, Callable[..., list[Need]]]] = MappingProxyType(
    {
        LawMetrics: needs_law,
        SecurityMetrics: needs_security,
        LedgerMetrics: needs_ledger,
        SignalMetrics: needs_signals,
    }
)


##### TYPES #####
class PlaneNeeds:
    """Satisfies PlaneNodePort; reads only the ledger."""

    __slots__ = ()

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.DECIDE, summary="the subject's needs: every reason found to enhance it", guard=Guard.SETTLED
    )

    @staticmethod
    def read(run: NodeRun) -> list[Need]:
        """One ledger row, as the needs it states."""
        match run:
            case NodeRun(status=Status.IDLE, reason=reason) if reason in UNCOVERED:
                return [Need("coverage", run.node, reason)]
            case NodeRun(status=Status.FAIL | Status.ERROR, metrics=None):
                return [Need("broken", run.node, run.reason)]
            case NodeRun(metrics=metrics) if (reader := READERS.get(type(metrics))) is not None:
                return reader(run, metrics)
            case _:
                return []

    async def run(self, context: PlaneContext) -> Outcome:
        latest = {run.node: run for run in context.state.ledger.runs() if run.subject == context.subject}
        needs = tuple(need for node, run in latest.items() if node != NODE for need in self.read(run))
        return Outcome(status=Status.OK, metrics=NeedsMetrics(needs=needs))
