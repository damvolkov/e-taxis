"""adapters.command: one argv run as a child — stdout to a file, stdin closed, stderr relayed live, bounded in time.

Two properties of the agent CLIs make this shape mandatory, and each hides the other: stdout goes to a temp file
(a large reply overflows a pipe and surfaces as a silent truncation), and stdin is closed (an inherited terminal
makes a non-interactive run look like a hang). `echo` relays the child's stderr behind a prefix as it arrives, so a
nested run's live rows show inside the step that runs it. `env` overrides the environment the adapter was built
with; nothing here reads the process environment itself."""

import asyncio
import sys
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import anyio

from e_taxis.workflow.models.error import CommandError

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
TAIL: int = 400


##### TYPES #####
class ShellCommand:
    """Satisfies CommandPort."""

    __slots__ = ("_environ",)

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = dict(environ)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_relay(line: bytes, echo: str) -> bytes:
        _ = echo and sys.stderr.write(f"{echo}{line.decode(errors='replace').rstrip()}\n")
        return line

    @classmethod
    async def _run_drain(cls, stream: asyncio.StreamReader, echo: str) -> bytes:
        return b"".join([cls._run_relay(line, echo) async for line in stream])

    @staticmethod
    async def _run_kill(process: asyncio.subprocess.Process) -> None:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()

    async def _run_spawn(
        self, argv: tuple[str, ...], sink: Path, cwd: Path | None, env: Mapping[str, str] | None
    ) -> asyncio.subprocess.Process:
        try:
            with sink.open("wb") as handle:
                return await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=handle,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._environ | dict(env or {}),
                    cwd=cwd,
                )
        except OSError as exc:
            msg = f"{argv[0]}: cannot start: {exc.strerror}"
            raise CommandError(msg) from exc

    ############################################################

    ##### PUBLIC #####

    async def run(
        self,
        *argv: str,
        limit: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        echo: str = "",
    ) -> str:
        with TemporaryDirectory(prefix="e-taxis-command-") as tmp:
            sink = Path(tmp) / "stdout"
            process = await self._run_spawn(argv, sink, cwd, env)
            try:
                async with asyncio.timeout(limit):
                    stderr, _ = await asyncio.gather(
                        self._run_drain(process.stderr or asyncio.StreamReader(), echo), process.wait()
                    )
            except TimeoutError:
                await self._run_kill(process)
                msg = f"{argv[0]}: timeout after {limit}s"
                raise CommandError(msg) from None
            stdout = await anyio.Path(sink).read_text(errors="replace")
        match process.returncode:
            case 0:
                return stdout
            case code:
                tail = (stderr.decode(errors="replace") or stdout)[-TAIL:]
                msg = f"{argv[0]} exited {code}: {tail}"
                raise CommandError(msg, code, stdout)
