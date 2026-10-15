"""models.error: the typed failure tree of the cli — every error a command raises carries its own exit code.

The launcher catches the root once and prints the message: a command raises, it never prints a failure
or calls `sys.exit` itself."""

from typing import ClassVar


##### ROOT #####
class CliError(Exception):
    """All expected cli failures. Anything else is a bug and keeps its traceback."""

    exit_code: ClassVar[int] = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


##### SPECIFIC #####
class JournalError(CliError):
    """The journal has nothing to undo."""

    exit_code: ClassVar[int] = 4


class CatalogError(CliError):
    """The catalog does not load: a file fails its schema, or the `requires` graph is not a DAG."""

    exit_code: ClassVar[int] = 5


class CatalogCycleError(CatalogError):
    """`requires` loops back on itself: no install order exists."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__(f"requires cycle: {' → '.join(cycle)}")


class SourceError(CliError):
    """The wanted parts cannot be read: no such profile, no e-engineer checkout, or not exactly one source."""

    exit_code: ClassVar[int] = 6


class PlanError(CliError):
    """The plan names parts it cannot install: unknown to the catalog, or blocked on a gate."""

    exit_code: ClassVar[int] = 7


class VerifyError(CliError):
    """At least one part failed its verify."""

    exit_code: ClassVar[int] = 8


class DoctorError(CliError):
    """The catalog breaks an integrity rule."""

    exit_code: ClassVar[int] = 9
