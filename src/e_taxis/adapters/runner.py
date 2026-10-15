"""adapters.runner: one argv run as a child process — no shell, stdin closed, stdout and stderr folded.

The writing side's only way to run a command (`uv tool install`, `npm install -g`, `claude mcp add-json`):
argv in, so nothing a catalog value holds is ever re-parsed by a shell. Stdin is closed, so a CLI that
would prompt fails instead of hanging. A cancelled run kills its child before the cancellation propagates."""

import asyncio
import shlex
from asyncio.subprocess import DEVNULL, PIPE, STDOUT
from contextlib import suppress

from e_taxis.models.error import RunnerError

##### DEFAULTS #####
TAIL: int = 3


##### TYPES #####
class ProcessRunner:
    """Satisfies RunnerPort."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_failure(argv: tuple[str, ...], code: int, output: str) -> RunnerError:
        tail = " · ".join(output.strip().splitlines()[-TAIL:])
        return RunnerError(f"`{shlex.join(argv)}` exited {code}" + (f": {tail}" if tail else ""))

    ############################################################

    ##### PUBLIC #####

    async def run(self, argv: tuple[str, ...]) -> str:
        try:
            process = await asyncio.create_subprocess_exec(*argv, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT)
        except OSError as exc:
            msg = f"`{shlex.join(argv)}` cannot start: {exc.strerror}"
            raise RunnerError(msg) from exc
        try:
            raw, _ = await process.communicate()
        finally:
            ### a cancelled communicate leaves the child running: it dies here, before the cancellation moves on.
            match process.returncode:
                case None:
                    with suppress(ProcessLookupError):
                        process.kill()
                    await process.wait()
                case _:
                    pass
        output = raw.decode(errors="replace")
        match process.returncode:
            case 0:
                return output
            case code:
                raise self._run_failure(argv, code or 0, output)
