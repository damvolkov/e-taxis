"""models.metrics: the typed evidence a step leaves in the ledger — an agent session's narrative, a loop check."""

from enum import StrEnum

from msgspec import Struct


##### TYPES #####
class SessionMetrics(Struct, frozen=True, tag="session"):
    """A step's run: who ran it (`run` for a command) and the last lines it said."""

    agent: str
    narrative: tuple[str, ...]


class LoopState(StrEnum):
    """What one `until` check of a bounded loop concluded."""

    CLOSED = "closed"
    OPEN = "open"
    STALLED = "stalled"

    @property
    def ends(self) -> bool:
        """Whether the loop stops here: done, or the same open set as the check before."""
        return self is not LoopState.OPEN


class LoopMetrics(Struct, frozen=True, tag="loop"):
    """One `until` check: its iteration, its conclusion, how much stayed open and a digest of it."""

    iteration: int
    state: LoopState
    open: int
    digest: str


type Metrics = SessionMetrics | LoopMetrics
