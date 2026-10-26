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
