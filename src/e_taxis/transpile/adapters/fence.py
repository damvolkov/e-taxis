"""adapters.fence: Landlock around every process a trial runs — read the world, write only the sandbox.

Pointing a harness at a sandbox (HOME, its config dir) tells it where to write; the fence makes that the only place
it *can* write, and the only TCP it may open is the fake model's port. `landrun` is Landlock's CLI (no user
namespace needed, which AppArmor denies here). The kernel offers an older ABI than landrun asks, so it runs
`--best-effort` — and a best effort that silently weakens is no fence, which is why `canary` proves it holds before
anything trusts it. landrun hands the fenced process an empty environment and splits `--env` values on commas, so
`env -i` inside the fence sets the environment whole: nothing inherited, every value intact, all of it in the argv.
A process that outlives its timeout is killed with its whole group: no phantom survives a trial."""

import asyncio
import os
import shutil
import signal
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

import anyio

from e_taxis.transpile.models.trial import TrialRun

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence
    from pathlib import Path

##### DEFAULTS #####
### writable beside the sandbox: the devices every CLI writes to.
DEVICES: Final[tuple[str, ...]] = ("/dev/null", "/dev/tty")
### how much of each stream a run keeps: the tail is where a failure explains itself.
TAIL: int = 4000
ENV: str = "/usr/bin/env"


##### TYPES #####
class LandrunFence:
    """Satisfies FencePort over the landrun binary."""

    __slots__ = ("_binary",)

    def __init__(self, binary: Path) -> None:
        self._binary = binary

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_kill(process: asyncio.subprocess.Process) -> None:
        """The process and every child it spawned; one already gone is not an error."""
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    ############################################################

    ##### PUBLIC #####

    def wrap(
        self,
        argv: Sequence[str],
        *,
        writable: Sequence[Path],
        ports: Sequence[int],
        env: Mapping[str, str],
        binds: Sequence[int] = (),
        network: bool = False,
    ) -> list[str]:
        """The argv to run fenced: read and execute `/`, write only `writable`, connect only to `ports` (any port when
        `network`), listen on `binds`."""
        return [
            str(self._binary),
            "--best-effort",
            "--ignore-missing",
            "--rox",
            "/",
            *(flag for path in (*map(str, writable), *DEVICES) for flag in ("--rw", path)),
            *(flag for port in ports for flag in ("--connect-tcp", str(port))),
            *(flag for port in binds for flag in ("--bind-tcp", str(port))),
            *(("--unrestricted-network",) if network else ()),
            "--",
            ENV,
            "-i",
            *(f"{name}={value}" for name, value in env.items()),
            *argv,
        ]

    @asynccontextmanager
    async def serve(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        writable: Sequence[Path],
        ports: Sequence[int],
        binds: Sequence[int],
    ) -> AsyncIterator[None]:
        """A fenced service kept up for the block, then killed with its whole group: no phantom outlives a probe."""
        binary = shutil.which(argv[0], path=env.get("PATH")) or argv[0]
        process = await asyncio.create_subprocess_exec(
            *self.wrap([binary, *argv[1:]], writable=writable, ports=ports, env=env, binds=binds),
            env={},
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            yield
        finally:
            self._run_kill(process)
            await process.wait()

    async def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        writable: Sequence[Path],
        ports: Sequence[int],
        limit: float,
        network: bool = False,
    ) -> TrialRun:
        """One process with exactly `env`, resolved on the PATH `env` declares; never raises — the run says how it ended."""
        started = time.monotonic()
        binary = shutil.which(argv[0], path=env.get("PATH")) or argv[0]
        wrapped = self.wrap([binary, *argv[1:]], writable=writable, ports=ports, env=env, network=network)
        process = await asyncio.create_subprocess_exec(
            *wrapped,
            env={},
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), limit)
            code = process.returncode
        except TimeoutError:
            self._run_kill(process)
            out, err = await process.communicate()
            code = None
        return TrialRun(
            argv=tuple(argv),
            code=code,
            seconds=round(time.monotonic() - started, 3),
            stdout=out.decode(errors="replace"),
            stderr=err.decode(errors="replace")[-TAIL:],
        )

    async def canary(self, inside: Path, outside: Path) -> bool:
        """Whether the fence holds: a write inside lands, a write outside is refused."""
        await anyio.Path(inside).mkdir(parents=True, exist_ok=True)
        env = {"PATH": "/usr/bin:/bin"}
        landed, refused = [
            await self.run(
                ["sh", "-c", f": > '{target}'"], env=env, cwd=inside, writable=[inside], ports=[], limit=30.0
            )
            for target in (inside / "canary", outside)
        ]
        held = landed.code == 0 and refused.code != 0 and await anyio.Path(inside / "canary").is_file()
        leaked = await anyio.Path(outside).exists()
        await anyio.Path(outside).unlink(missing_ok=True)
        return held and not leaked
