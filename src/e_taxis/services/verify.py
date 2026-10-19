"""services.verify: does each part work — every resolved entry's `verify`, run; all of them, not fail-fast.

A part the catalog does not know has no verify, so it cannot pass: it is reported failed, never skipped."""

import asyncio
from typing import TYPE_CHECKING

from e_taxis.models.verify import VerifyReport, VerifyResult

if TYPE_CHECKING:
    from e_taxis.adapters.ports import ProbePort, SourcePort
    from e_taxis.models.catalog import Target
    from e_taxis.services.resolver import ResolverService


##### TYPES #####
class VerifyService:
    """Resolver for the join, ProbePort to run each verify."""

    __slots__ = ("_probe", "_resolver")

    def __init__(self, resolver: ResolverService, probe: ProbePort) -> None:
        self._resolver = resolver
        self._probe = probe

    async def run(self, source: SourcePort, target: Target) -> VerifyReport:
        resolution = await self._resolver.resolve(source, target)
        probes = await asyncio.gather(*(self._probe.run(item.entry.verify) for item in resolution.resolved))
        return VerifyReport(
            target=target,
            results=(
                *(
                    VerifyResult(id=item.entry.id, passed=probe.present, detail=probe.detail)
                    for item, probe in zip(resolution.resolved, probes, strict=True)
                ),
                *(
                    VerifyResult(id=part.id, passed=False, detail=f"no catalog entry · wanted by {part.source}")
                    for part in resolution.unknown
                ),
            ),
        )
