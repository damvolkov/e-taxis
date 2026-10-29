"""assess.stats: the paired difference on the plan's primary metric, its interval, and what it says — pure, seeded.

The arms ran interleaved, so the candidate's and the baseline's runs of one case and repetition are a pair: they
shared the machine's state at that moment. The statistic is the mean of the paired differences (candidate -
baseline, in the metric's units); its interval is the planes' own seeded paired bootstrap (`engine.stats`,
`interval_bootstrap`, the effect A/B's: each pair one cluster, `resamples` draws, stdlib only — no scipy, no BCa).
The interval is read against the pre-registered threshold in the plan's direction: it clears the threshold →
better, it clears minus the threshold → worse, anything else → no difference. Without a measured pair the outcome is
`not measured`, with the reason. Secondary metrics are described as medians per arm, never deciding."""

from statistics import median
from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.engine.stats import interval_bootstrap
from e_taxis.workflow.models.assess import ArmSamples, Outcome, Plan, Samples, Stats

if TYPE_CHECKING:
    from collections.abc import Sequence

##### DEFAULTS #####
RESAMPLES: int = 10_000
CONFIDENCE: float = 0.95


##### TYPES #####
class AssessStats:
    """Stateless but for the bootstrap's size and confidence."""

    __slots__ = ("_confidence", "_resamples")

    def __init__(self, resamples: int = RESAMPLES, confidence: float = CONFIDENCE) -> None:
        self._resamples = resamples
        self._confidence = confidence

    ##### PRIVATE METHODS #####

    @staticmethod
    def _compare_unmeasured(plan: Plan, samples: Samples, arms: dict[str, ArmSamples]) -> str:
        """Why nothing can be compared; empty when the two arms share at least one measured pair."""
        sides = (plan.candidate.name, plan.baseline.name)
        broken = [
            f"{name} not installed ({arms[name].error})" for name in sides if name in arms and not arms[name].installed
        ]
        absent = [f"{name} never ran" for name in sides if name not in arms]
        return samples.reason or "; ".join((*absent, *broken))

    @staticmethod
    def _compare_pairs(candidate: ArmSamples, baseline: ArmSamples) -> tuple[list[list[float]], list[list[float]]]:
        """(baseline, candidate) as one-run clusters, for every (case, repetition) both measured, in a stable order."""
        theirs = {(s.case, s.rep): s.metric for s in baseline.samples if s.metric is not None}
        ours = {(s.case, s.rep): s.metric for s in candidate.samples if s.metric is not None}
        keys = sorted(ours.keys() & theirs.keys())
        return [[theirs[key]] for key in keys], [[ours[key]] for key in keys]

    @staticmethod
    def _compare_outcome(plan: Plan, low: float, high: float) -> Outcome:
        """The interval in the plan's direction (a gain is positive), against ± the threshold."""
        gain = sorted((low, high) if plan.higher_is_better else (-high, -low))
        match (gain[0] > plan.threshold, gain[1] < -plan.threshold):
            case (True, _):
                return Outcome.BETTER
            case (_, True):
                return Outcome.WORSE
            case _:
                return Outcome.SAME

    @staticmethod
    def _compare_secondary(plan: Plan, arms: Sequence[ArmSamples]) -> dict[str, str]:
        """Each secondary metric's median per arm, and how many runs of each arm measured the primary."""
        named = dict.fromkeys((*plan.secondary, *(k for arm in arms for s in arm.samples for k in s.secondary)))
        described = {
            key: " · ".join(
                f"{arm.name} {median(values):g} (n={len(values)})" if values else f"{arm.name} not reported"
                for arm in arms
                for values in ([s.secondary[key] for s in arm.samples if key in s.secondary],)
            )
            for key in named
        }
        runs = " · ".join(
            f"{arm.name} {sum(s.metric is not None for s in arm.samples)}/{len(arm.samples)} measured" for arm in arms
        )
        return {**described, "runs": runs}

    ############################################################

    ##### PUBLIC #####

    def compare(self, plan: Plan, samples: Samples) -> Stats:
        """The candidate against the baseline on the plan's primary metric."""
        arms = {arm.name: arm for arm in samples.arms}
        candidate, baseline = plan.candidate.name, plan.baseline.name
        frame = Stats(
            metric=plan.metric,
            outcome=Outcome.UNMEASURED,
            candidate=candidate,
            baseline=baseline,
            threshold=plan.threshold,
            higher_is_better=plan.higher_is_better,
        )
        base, ours = (
            ([], [])
            if (why := self._compare_unmeasured(plan, samples, arms))
            else self._compare_pairs(arms[candidate], arms[baseline])
        )
        match ours:
            case []:
                return msgspec.structs.replace(frame, reason=why or "no pair measured by both arms")
            case _:
                mean, low, high = interval_bootstrap(base, ours, self._resamples, 1 - self._confidence, plan.seed)
                return msgspec.structs.replace(
                    frame,
                    outcome=self._compare_outcome(plan, low, high),
                    pairs=len(ours),
                    mean=mean,
                    low=low,
                    high=high,
                    resamples=self._resamples,
                    confidence=self._confidence,
                    secondary=self._compare_secondary(plan, samples.arms),
                )
