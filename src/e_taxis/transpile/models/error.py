"""models.error: the transpiler's failure tree — each one a CliError with its own exit code."""

from typing import ClassVar

from e_taxis.harness.models.error import CliError


##### TYPES #####
class TranspileError(CliError):
    """Root of every transpiler failure."""

    exit_code: ClassVar[int] = 17


class SchemaError(TranspileError):
    """A type expression that does not parse, a name declared nowhere, or a value its type refuses."""

    exit_code: ClassVar[int] = 18


class NousError(TranspileError):
    """An e-nous checkout that cannot be read at the asked ref: git, a missing file, unparsable YAML."""

    exit_code: ClassVar[int] = 19


class CheckError(TranspileError):
    """`transpile check` found blocking findings: the report is printed, then this carries the count."""

    exit_code: ClassVar[int] = 20
