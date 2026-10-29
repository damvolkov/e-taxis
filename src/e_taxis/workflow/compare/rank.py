"""compare.rank: one rubric over incumbents and rivals — which rival, if any, earns a bench against its incumbent.

Every subject gets terms in [0, 1], weighted: `rust` the compiled hot path the house prefers (0.25); `recency` the
last release, 1 today down to 0 a year old (0.15); `cadence` releases a year, 12 or more counting full (0.10);
`dependents` and `downloads`, log-scaled to 10⁴ dependents and 10⁷ downloads a month (0.15 each); `scorecard` the
OpenSSF score over 10 (0.10); `licence` 1 when permissive (0.10). A KPI no source gave scores 0 and is named in
`unmeasured`: an unknown is never a strength. Stars never score — they break a tie between rivals, nothing more.

Per incumbent the best rival is kept when its total beats the incumbent's by `margin`; the others, and an incumbent
with no rival worth a bench, are kept by the rubric — `keep`, with the reason."""

import datetime as dt
import math
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from e_taxis.workflow.models.compare import Contest, Score, Shortlist

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.workflow.models.compare import Healths, Rivalry, Rivals, Vital

##### DEFAULTS #####
WEIGHTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "rust": 0.25,
        "recency": 0.15,
        "cadence": 0.10,
        "dependents": 0.15,
        "downloads": 0.15,
        "scorecard": 0.10,
        "licence": 0.10,
    }
)
MARGIN: float = 0.05
PERMISSIVE: Final[frozenset[str]] = frozenset(
    {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MPL-2.0", "0BSD", "Unlicense", "Zlib"}
)


##### TYPES #####
class CompareRank:
    """The rubric; `now` is the day recency is measured from."""

    __slots__ = ("_margin", "_now", "_weights")

    def __init__(self, now: dt.datetime, weights: Mapping[str, float] = WEIGHTS, margin: float = MARGIN) -> None:
        self._now = now
        self._weights = weights
        self._margin = margin

    ##### PRIVATE METHODS #####

    def _score_terms(self, vital: Vital) -> dict[str, float | None]:
        """Each term in [0, 1], or None when its KPI was not measured."""
        health = vital.health
        released = dt.datetime.fromisoformat(health.last_release) if health.last_release else None
        age = (self._now - released).days if released else None
        return {
            "rust": 1.0 if vital.rust else 0.0,
            "recency": max(0.0, 1 - age / 365) if age is not None else None,
            "cadence": min(health.releases_per_year / 12, 1.0) if health.releases_per_year is not None else None,
            "dependents": min(math.log10(health.dependents + 1) / 4, 1.0) if health.dependents is not None else None,
            "downloads": (
                min(math.log10(health.downloads_month + 1) / 7, 1.0) if health.downloads_month is not None else None
            ),
            "scorecard": health.scorecard / 10 if health.scorecard is not None else None,
            "licence": (1.0 if health.license in PERMISSIVE else 0.0) if health.license else None,
        }

    def _score(self, vital: Vital) -> Score:
        terms = self._score_terms(vital)
        weighted = {name: round(self._weights[name] * (term or 0.0), 4) for name, term in terms.items()}
        return Score(
            name=vital.name,
            total=round(sum(weighted.values()), 4),
            terms=weighted,
            unmeasured=tuple(name for name, term in terms.items() if term is None),
            stars=vital.stars,
        )

    def _contest(self, rivalry: Rivalry, scores: Mapping[str, Score]) -> Contest:
        """One incumbent against its rivals: the best one, by total then stars, if it clears the margin."""
        incumbent = scores[rivalry.incumbent.name]
        ranked = sorted(
            (scores[rival.name] for rival in rivalry.rivals),
            key=lambda score: (score.total, score.stars or 0),
            reverse=True,
        )
        best = ranked[0] if ranked else None
        wins = best is not None and best.total > incumbent.total + self._margin
        reason = (
            f"{best.name} scores {best.total} against {incumbent.total} (margin {self._margin})"
            if best
            else "no rival named"
        )
        return Contest(
            incumbent=incumbent.name,
            role=rivalry.role,
            scores=(incumbent, *ranked),
            reason=reason if wins else f"kept by the rubric: {reason}",
            rival=best.name if best and wins else "",
        )

    ############################################################

    ##### PUBLIC #####

    def rank(self, rivals: Rivals, healths: Healths) -> Shortlist:
        """Every contest; a contest's `rival` empty is an incumbent kept without a bench."""
        scores = {vital.name: self._score(vital) for vital in healths.subjects}
        return Shortlist(
            weights=dict(self._weights),
            margin=self._margin,
            contests=tuple(self._contest(rivalry, scores) for rivalry in rivals.incumbents),
        )
