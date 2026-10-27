"""models.verdict: what an enhancement concluded about each subject, and what a promotion did with it."""

import datetime as dt
from enum import StrEnum, auto

from msgspec import Struct


##### TYPES #####
class Decision(StrEnum):
    """The five endings of a subject, heaviest first in `WEIGHT`.

    `adopt` every gate green and the grade within the entity's ceiling · `propose` green, a human decides · `hold`
    evidence missing or inconclusive · `reject` a gate is red · `settled` no proposer changed anything."""

    ADOPT = auto()
    PROPOSE = auto()
    HOLD = auto()
    REJECT = auto()
    SETTLED = auto()

    @property
    def promotable(self) -> bool:
        return self in {Decision.ADOPT, Decision.PROPOSE}


class Verdict(Struct, frozen=True, kw_only=True):
    """One subject, concluded, with the ledger rows that back it and the patch a promotion would apply."""

    subject: str
    decision: Decision
    reasons: tuple[str, ...]
    grade: str = ""
    bump: str = ""
    patch: str = ""
    evidence: tuple[str, ...] = ()


class Promotion(Struct, frozen=True, kw_only=True):
    """What `enhance promote` applied to the checkout, against which base."""

    run_id: str
    base_sha: str
    at: dt.datetime
    applied: tuple[str, ...]
    already: tuple[str, ...] = ()
    refused: dict[str, str] = {}
