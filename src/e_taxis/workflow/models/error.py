"""models.error: the workflow branch's failure tree — each one a CliError with its own exit code."""

from typing import ClassVar

from e_taxis.harness.models.error import CliError


##### TYPES #####
class WorkflowError(CliError):
    """Root: a workflow that cannot be read or bound — unknown id, a static problem, an undeclared parameter."""

    exit_code: ClassVar[int] = 23


class RunFailedError(WorkflowError):
    """The run finished and at least one step failed or broke: the report is printed, then this carries the count."""

    exit_code: ClassVar[int] = 24


class CommandError(WorkflowError):
    """A command exited non-zero or timed out; `code` is its exit status (None on a timeout), `stdout` what it said."""

    exit_code: ClassVar[int] = 26

    def __init__(self, message: str, code: int | None = None, stdout: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.stdout = stdout


class AgentError(CommandError):
    """An agent that cannot be driven headless: absent from the tree, a subagent, or a fence that does not hold."""


class DistillError(WorkflowError):
    """A reverse-distill step that cannot go on: a missing or malformed artifact, a refused input."""

    exit_code: ClassVar[int] = 25


class NothingError(DistillError):
    """The branches carry no commit past their base: nothing to distill. The step node reads exit 3 as `skip`."""

    exit_code: ClassVar[int] = 3


class UnknownSlotError(DistillError):
    """A slot no row of the versioning matrix judges: the table is behind the corpus."""


class LockError(WorkflowError):
    """Another run held the e-nous checkout past the wait (EX_TEMPFAIL: try again later)."""

    exit_code: ClassVar[int] = 75


class PlaneError(WorkflowError):
    """An evaluation or enhancement that cannot start or be read: no graph, an unknown subject or node, no such run."""

    exit_code: ClassVar[int] = 27


class ReasonError(PlaneError):
    """An enhancement asked for without a reason on record, or over uncommitted edits it was not told to take."""

    exit_code: ClassVar[int] = 28


class HumanError(PlaneError):
    """A human command run without a human: no terminal and no mandate handed down, or inside a headless session."""

    exit_code: ClassVar[int] = 29


class StaleError(PlaneError):
    """A promotion refused: HEAD moved since the run's base, so its measurements no longer describe the checkout."""

    exit_code: ClassVar[int] = 30


class NeedsOpenError(PlaneError):
    """`eval needs` found open needs: exit 1, the `until` check's reading of "still open"."""

    exit_code: ClassVar[int] = 1


class RefusedError(PlaneError):
    """A promotion applied what it could and refused at least one patch: exit 1, after the record is written."""

    exit_code: ClassVar[int] = 1


class IdleError(PlaneError):
    """An enhancement with nothing to act on: no subject has a need. Exit 3, the workflow step's `skip`."""

    exit_code: ClassVar[int] = 3


class ProviderError(PlaneError):
    """A tier, alias or key the checkout's models config does not resolve, or an endpoint that answered no message."""
