"""plane.intake: no reason, no enhancement — the needs the source evaluation stated for this subject (`--from`),
your directive, and `--manual`. With none of them the subject is `idle`: every proposer after it idles, and the
verdict is `settled`."""

from typing import TYPE_CHECKING, ClassVar

from e_taxis.workflow.models.metrics import BriefMetrics, NeedsMetrics
from e_taxis.workflow.models.plane import Guard, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from e_taxis.workflow.models.ports import LedgerPort, PlaneContext

##### DEFAULTS #####
NEEDS: str = "needs"
LEDGER: str = "ledger.jsonl"
NOTHING: str = "nothing to act on: no need, no directive"


##### TYPES #####
class PlaneIntake:
    """Satisfies PlaneNodePort; `ledgers` opens the source evaluation's ledger beside this run's folder."""

    __slots__ = ("_ledgers",)

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE,
        summary="the evaluation's needs, your directive, --manual: the only reasons to act",
        guard=Guard.SETTLED,
    )

    def __init__(self, ledgers: Callable[[Path], Awaitable[LedgerPort]]) -> None:
        self._ledgers = ledgers

    async def run(self, context: PlaneContext) -> Outcome:
        manifest = context.state.manifest
        source = context.state.paths.root.parent / manifest.source / LEDGER
        row = (await self._ledgers(source)).latest(NEEDS, context.subject) if manifest.source else None
        match row:
            case NodeRun(metrics=NeedsMetrics(needs=needs)):
                pass
            case _:
                needs = ()
        brief = BriefMetrics(source=manifest.source, needs=needs, directive=manifest.directive, manual=manifest.manual)
        acts = bool(needs or manifest.directive or manifest.manual)
        return Outcome(status=Status.OK if acts else Status.IDLE, metrics=brief, reason="" if acts else NOTHING)
