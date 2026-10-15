"""models.session: what one invocation knows before its command runs — sealed into the state graph."""

from dataclasses import dataclass


##### TYPES #####
@dataclass(frozen=True, slots=True)
class Session:
    """The run: its command path and its verbosity."""

    command: str
    verbose: bool = False
