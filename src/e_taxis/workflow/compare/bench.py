"""compare.bench: every shortlisted pair benched the way radar-tech benches one candidate — one fenced sandbox per arm.

The pairs run one after another: two installs racing for the same machine would bias both. `skip` (bench=false)
installs nothing, every pair recorded not measured."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.compare import Benched, PairSamples

if TYPE_CHECKING:
    import datetime as dt

    from e_taxis.workflow.assess.bench import AssessBench
    from e_taxis.workflow.models.compare import Plans


class CompareBench:
    """radar-tech's bench, per pair."""

    __slots__ = ("_bench",)

    def __init__(self, bench: AssessBench) -> None:
        self._bench = bench

    async def run(self, plans: Plans, *, skip: bool, now: dt.datetime) -> PairSamples:
        return PairSamples(
            pairs=tuple(
                [
                    Benched(
                        incumbent=pair.incumbent,
                        rival=pair.rival,
                        samples=await self._bench.run(pair.plan, skip=skip, now=now),
                    )
                    for pair in plans.pairs
                ]
            )
        )
