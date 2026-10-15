"""services.plan: what apply would do — every resolved part probed, compared with its pin, gated, decided.

Read-only: the plan runs each entry's `probe` and nothing else. A part already present (and on its pin,
when the source pins it) is skipped; absent is install; present off-pin is update. Install and update
stop at a gate that needs a human — a licence, secrets or a confirmation — as `blocked`. Parts the
catalog does not know close the plan as `unknown`."""

import asyncio
from typing import TYPE_CHECKING

from e_taxis.models.plan import Plan, PlanAction, PlanStep

if TYPE_CHECKING:
    from e_taxis.adapters.ports import ProbePort, SourcePort
    from e_taxis.models.catalog import CatalogGate, Target
    from e_taxis.models.plan import Probe, Resolved
    from e_taxis.services.resolver import ResolverService


##### TYPES #####
class PlanService:
    """Resolver for the join, ProbePort for the world as it is."""

    __slots__ = ("_probe", "_resolver")

    def __init__(self, resolver: ResolverService, probe: ProbePort) -> None:
        self._resolver = resolver
        self._probe = probe

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_need(pin: str | None, probe: Probe) -> tuple[PlanAction, str]:
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
    def _run_gate(gate: CatalogGate) -> str:
        held = (
            f"licence {gate.licence}" if gate.licence else "",
            f"secrets {', '.join(gate.secrets)}" if gate.secrets else "",
            "confirm" if gate.confirm else "",
        )
        return f"gate: {' · '.join(part for part in held if part)}"

    def _run_step(self, resolved: Resolved, probe: Probe) -> PlanStep:
        action, reason = self._run_need(resolved.wanted.pin, probe)
        blocked = action is not PlanAction.SKIP and resolved.entry.gate.needed
        return PlanStep(
            id=resolved.entry.id,
            action=PlanAction.BLOCKED if blocked else action,
            reason=self._run_gate(resolved.entry.gate) if blocked else reason,
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, source: SourcePort, target: Target) -> Plan:
        resolution = await self._resolver.resolve(source, target)
        probes = await asyncio.gather(*(self._probe.run(item.entry.probe) for item in resolution.resolved))
        return Plan(
            target=target,
            steps=(
                *(self._run_step(item, probe) for item, probe in zip(resolution.resolved, probes, strict=True)),
                *(
                    PlanStep(
                        id=part.id, action=PlanAction.UNKNOWN, reason=f"no catalog entry · wanted by {part.source}"
                    )
                    for part in resolution.unknown
                ),
            ),
        )
