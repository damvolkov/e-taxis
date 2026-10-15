"""models.error: the typed failure tree of the cli — every error a command raises carries its own exit code.

The launcher catches the root once and prints the message: a command raises, it never prints a failure
or calls `sys.exit` itself."""

from typing import ClassVar

from e_taxis.models.journal import JournalEffect


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


class ApplyError(CliError):
    """Apply refused before writing (unknown parts, an unmet gate, `--only` naming no step), or a step or verify failed."""

    exit_code: ClassVar[int] = 10


class UninstallError(CliError):
    """Uninstall named no entry serving the target, or a step failed."""

    exit_code: ClassVar[int] = 11


class CoreError(CliError):
    """The core cannot be read: no checkout, a ref git cannot archive, a manifest that fails its contract."""

    exit_code: ClassVar[int] = 13


class BrainError(CliError):
    """The brain cannot be installed: no projection for the target, or a write failed — undo reaches what landed."""

    exit_code: ClassVar[int] = 14


##### PRIMITIVES #####
class PrimitiveError(CliError):
    """A primitive could not finish. `effects` is what it had already changed: the journal keeps it for undo.

    The services turn it into a failed step; it reaches the launcher only from `history undo`."""

    exit_code: ClassVar[int] = 12

    def __init__(self, message: str, effects: tuple[JournalEffect, ...] = ()) -> None:
        super().__init__(message)
        self.effects = effects


class RecipeError(PrimitiveError):
    """A recipe's `with` does not fit its primitive's schema."""


class DigestError(PrimitiveError):
    """A download has no sha256 to check, or does not match it."""


class DownloadError(PrimitiveError):
    """A download failed: status, connection, timeout."""


class RunnerError(PrimitiveError):
    """A command exited non-zero, or could not start."""


class OwnsError(PrimitiveError):
    """A settings recipe writes a key its entry does not list in `owns`."""


class SettingsError(PrimitiveError):
    """A settings file cannot take the merge: its root or a parent of the key is not a JSON object."""


class JsoncError(SettingsError):
    """A settings file is not plain JSON — comments or trailing commas a rewrite would destroy."""
