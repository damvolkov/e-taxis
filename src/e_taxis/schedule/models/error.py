"""models.error: the schedule branch's failure tree — each one a CliError with its own exit code."""

from typing import ClassVar

from e_taxis.harness.models.error import CliError


##### TYPES #####
class ScheduleError(CliError):
    """Root: schedules that cannot be read, validated or carried out — an off-shape declaration, a calendar systemd
    refuses, an id not declared or not installed, a systemctl call that failed. Nothing is written past a refusal."""

    exit_code: ClassVar[int] = 32


class ScheduleRunError(ScheduleError):
    """`schedule run` finished and the service's result is not `success`: the state is printed, then this."""

    exit_code: ClassVar[int] = 33
