"""adapters.probe: a catalog entry's `probe` or `verify`, run in a shell — bounded, timed out, output captured.

The command comes from the catalog and is read-only by contract (design §4): this adapter runs it, it
does not vet it. stderr is folded into stdout, since tools disagree on where `--version` prints."""

import asyncio
import os
import signal
from asyncio.subprocess import DEVNULL, PIPE, STDOUT, Process
from contextlib import suppress

from e_taxis.harness.models.plan import Probe

##### DEFAULTS #####
LIMIT: int = 8


##### TYPES #####
class ShellProbe:
    """Satisfies ProbePort; at most `limit` commands in flight, each killed at `timeout` seconds."""

    __slots__ = ("_gate", "_timeout")

    def __init__(self, timeout: float, limit: int = LIMIT) -> None:
        self._timeout = timeout
        self._gate = asyncio.Semaphore(limit)

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _run_reap(process: Process) -> None:
        """The shell's whole group is killed, then the shell waited for: a timed-out `sh -c` leaves no child behind.

        Killing the shell alone would orphan its children, and an orphan holding the pipe keeps the probe open."""
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()

    async def _run_shell(self, command: str) -> Probe:
        process = await asyncio.create_subprocess_shell(
            command, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, start_new_session=True
        )
        try:
            async with asyncio.timeout(self._timeout):
                output, _ = await process.communicate()
        except TimeoutError:
            return Probe(present=False, version=None, detail=f"timeout after {self._timeout}s")
        finally:
            await self._run_reap(process)
        first = next(iter(output.decode(errors="replace").splitlines()), "").strip()
        detail = f"exit {process.returncode}" + (f" · {first}" if first else "")
        return Probe(present=process.returncode == 0, version=first or None, detail=detail)

    ############################################################

    ##### PUBLIC #####

    async def run(self, command: str) -> Probe:
        async with self._gate:
            return await self._run_shell(command)
