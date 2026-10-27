"""plane.speckeeper: the spec maintainer agent as a proposer, confined to the sandbox.

It is briefed with the exact drift signals the source evaluation recorded for this backend (`--from`) — never
fetched again — and your directive when you give one; no signal and no directive is `idle`. It runs inside the run's
sandbox, so every edit lands there; what it touched is measured by git under the spec's place, never taken from its
narrative, and a session that wrote the real checkout is refused."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

import msgspec

from e_taxis.workflow.models.metrics import ProposalMetrics, SignalMetrics
from e_taxis.workflow.models.plane import Nature, NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from e_taxis.workflow.models.metrics import SignalRow
    from e_taxis.workflow.models.ports import AgentPort, LedgerPort, PlaneContext, SandboxPort

##### DEFAULTS #####
AGENT: str = "speckeeper"
SIGNALS: str = "signals"
LEDGER: str = "ledger.jsonl"
NOTHING: str = "no drift signal and no directive"
BRIEF: Final[str] = """\
Specs maintenance, in a sandbox. The signals below are the ones the spec evaluation \
(`taxis eval run spec`) recorded; they, and a directive when one follows, are the only \
admissible input. For each: classify it with `flow-gen-specs`, open the exact source it points at, \
and write rows — never code — into {place}. Touch nothing else, commit nothing. End with one line per \
file touched and one line per signal left alone, each with its reason.

Signals (JSON):
{signals}{directive}"""


##### TYPES #####
class PlaneSpeckeeper:
    """Satisfies PlaneNodePort over an agent and the sandbox; `limit` bounds one session."""

    __slots__ = ("_agent", "_ledgers", "_limit", "_sandbox")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.PROPOSE,
        summary="speckeeper session over the evaluation's signals, in the sandbox",
        nature=Nature.SEMANTIC,
    )

    def __init__(
        self, agent: AgentPort, sandbox: SandboxPort, ledgers: Callable[[Path], Awaitable[LedgerPort]], limit: float
    ) -> None:
        self._agent = agent
        self._sandbox = sandbox
        self._ledgers = ledgers
        self._limit = limit

    async def _run_signals(self, context: PlaneContext) -> tuple[SignalRow, ...]:
        source = context.state.manifest.source
        ledger = await self._ledgers(context.state.paths.root.parent / source / LEDGER) if source else None
        match ledger.latest(SIGNALS, context.subject) if ledger else None:
            case NodeRun(metrics=SignalMetrics(signals=rows)):
                return rows
            case _:
                return ()

    async def run(self, context: PlaneContext) -> Outcome:
        manifest, paths = context.state.manifest, context.state.paths
        rows = await self._run_signals(context)
        match (rows, manifest.directive):
            case ((), ""):
                return Outcome(status=Status.IDLE, reason=NOTHING)
            case _:
                pass
        place, nous = manifest.place(context.subject), Path(manifest.nous)
        directive = f"\n\nDirective from the maintainer (also admissible input):\n{manifest.directive}" * bool(
            manifest.directive
        )
        brief = BRIEF.format(
            place=place, signals=msgspec.json.format(msgspec.json.encode(rows)).decode(), directive=directive
        )
        before, _ = await self._sandbox.fingerprint(nous)
        reply = await self._agent.drive(AGENT, brief, cwd=paths.sandbox, limit=self._limit)
        after, dirty = await self._sandbox.fingerprint(nous)
        touched = await self._sandbox.dirty(paths.sandbox, place)
        escaped = "" if after == before else f"wrote into the real checkout: {', '.join(dirty)}"
        return Outcome(
            status=Status.FAIL if escaped else Status.OK,
            reason=escaped,
            tokens=reply.tokens,
            cached=reply.cached,
            runner="opencode",
            metrics=ProposalMetrics(proposer=AGENT, files=touched, lessons=tuple(row.detail for row in rows)),
        )
