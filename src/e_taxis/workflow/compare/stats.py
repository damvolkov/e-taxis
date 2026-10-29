"""compare.stats: every pair's paired interval, as radar-tech reads one — joined to its plan by (incumbent, rival)."""

from typing import TYPE_CHECKING

from e_taxis.workflow.models.compare import Measured, PairStats

if TYPE_CHECKING:
    from e_taxis.workflow.assess.stats import AssessStats
    from e_taxis.workflow.models.compare import PairSamples, Plans


class CompareStats:
    """radar-tech's stats, per pair; a pair with no samples is not measured."""

    __slots__ = ("_stats",)

    def __init__(self, stats: AssessStats) -> None:
        self._stats = stats

    def compare(self, plans: Plans, samples: PairSamples) -> PairStats:
        benched = {(pair.incumbent, pair.rival): pair.samples for pair in samples.pairs}
        return PairStats(
            pairs=tuple(
                Measured(
                    incumbent=pair.incumbent,
                    rival=pair.rival,
                    stats=self._stats.compare(pair.plan, benched[(pair.incumbent, pair.rival)]),
                )
                for pair in plans.pairs
                if (pair.incumbent, pair.rival) in benched
            )
        )
