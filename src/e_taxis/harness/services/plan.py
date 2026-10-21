"""services.plan: what apply would do — every resolved part probed, compared with its pin, gated, decided.

Read-only: the plan runs each entry's `probe` and nothing else. A part already present (and on its pin,
when the source pins it) is skipped; absent is install; present off-pin is update. Install and update
of what this phase does not write (compose, the project scope) are `deferred`; the rest stop at a gate
that needs a human — a licence, secrets or a confirmation — as `blocked`, holding the action back. Parts
the catalog does not know close the plan as `unknown`."""

import asyncio
from typing import TYPE_CHECKING

from e_taxis.harness.models.plan import Plan, PlanAction, PlanStep

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogGate, Target
    from e_taxis.harness.models.plan import Probe, Resolution, Resolved
    from e_taxis.harness.models.ports import ProbePort, SourcePort
    from e_taxis.harness.services.resolver import ResolverService


##### TYPES #####
class PlanService:
    """Resolver for the join, ProbePort for the world as it is."""

    __slots__ = ("_probe", "_resolver")

    def __init__(self, resolver: ResolverService, probe: ProbePort) -> None:
        self._resolver = resolver
        self._probe = probe

    ##### PRIVATE METHODS #####

    @staticmethod
    def _decide_need(pin: str | None, probe: Probe) -> tuple[PlanAction, str]:
        ### probes print `claude 2.1.3 (Claude Code)` or an image tag: the pin, `v` dropped, is looked for in the line.
        found = probe.version or ""
        match (probe.present, pin):
            case (False, _):
                return (PlanAction.INSTALL, f"absent · {probe.detail}")
            case (True, None):
                return (PlanAction.SKIP, f"present · {found or probe.detail}")
            case (True, str()) if pin.removeprefix("v") in found:
                return (PlanAction.SKIP, f"present · {found} matches pin {pin}")
            case _:
                return (PlanAction.UPDATE, f"found {found}, pin {pin}")

    @staticmethod
    def _decide_gate(gate: CatalogGate) -> str:
        held = (
            f"licence {gate.licence}" if gate.licence else "",
            f"secrets {', '.join(gate.secrets)}" if gate.secrets else "",
            "confirm" if gate.confirm else "",
        )
        return f"gate: {' · '.join(part for part in held if part)}"

    def _decide_step(self, resolved: Resolved, probe: Probe, target: Target) -> PlanStep:
        entry = resolved.entry
        action, reason = self._decide_need(resolved.wanted.pin, probe)
        match (action, entry.deferral(target), entry.gate.needed):
            case (PlanAction.SKIP, _, _):
                return PlanStep(id=entry.id, action=action, reason=reason)
            case (_, str() as deferred, _):
                return PlanStep(id=entry.id, action=PlanAction.DEFERRED, reason=deferred)
            case (_, None, True):
                return PlanStep(
                    id=entry.id, action=PlanAction.BLOCKED, reason=self._decide_gate(entry.gate), held=action
                )
            case _:
                return PlanStep(id=entry.id, action=action, reason=reason)

    ############################################################

    ##### PUBLIC #####

    async def run(self, source: SourcePort, target: Target) -> Plan:
        return await self.decide(await self._resolver.resolve(source, target), target)

    async def decide(self, resolution: Resolution, target: Target) -> Plan:
        """The plan for a resolution already in hand: every resolved part probed, in order."""
        probes = await asyncio.gather(*(self._probe.run(item.entry.probe) for item in resolution.resolved))
        return Plan(
            target=target,
            steps=(
                *(
                    self._decide_step(item, probe, target)
                    for item, probe in zip(resolution.resolved, probes, strict=True)
                ),
                *(
                    PlanStep(
                        id=part.id, action=PlanAction.UNKNOWN, reason=f"no catalog entry · wanted by {part.source}"
                    )
                    for part in resolution.unknown
                ),
            ),
        )
