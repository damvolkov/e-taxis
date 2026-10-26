"""models.trial: what a phantom harness showed — every fenced run, and per entity what reached its model.

A trial renders the core into a sandboxed home, raises the real harness there under a Landlock fence with a fake
model endpoint, and reads what the harness sent (or printed). `TrialSight` is one entity's evidence: how many of the
rendered tokens (persona slots, instance ids) the probes it names were expected to show, and which ones they did not."""

from msgspec import Struct


##### TYPES #####
class TrialRun(Struct, frozen=True, kw_only=True):
    """One fenced process: how it ended (`code` None when killed at its timeout), its output's tail."""

    argv: tuple[str, ...]
    code: int | None
    seconds: float
    stdout: str = ""
    stderr: str = ""


class TrialSight(Struct, frozen=True, kw_only=True):
    entity: str
    probes: tuple[str, ...]
    expected: int
    missing: tuple[str, ...] = ()

    @property
    def held(self) -> bool:
        return self.expected > 0 and not self.missing


class TrialReport(Struct, frozen=True, kw_only=True):
    """`captured` counts the capture probes that reached the fake model: zero means the harness never asked it."""

    backend: str
    runs: tuple[TrialRun, ...]
    sights: tuple[TrialSight, ...]
    captured: int

    @property
    def held(self) -> bool:
        return bool(self.sights) and all(sight.held for sight in self.sights)
