"""adapters.runner: async subprocess port — one command at a time, every output line streamed to an emitter."""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from pathlib import Path


##### TYPES #####
class CommandRunner:
    """Runs argv in cwd, merging stdout+stderr into ``emit`` line by line; answers the exit code."""

    async def run(self, argv: Sequence[str], cwd: Path, emit: Callable[[str], Awaitable[None]]) -> int:
        process = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        if process.stdout is not None:
            async for raw in process.stdout:
                await emit(raw.decode(errors="replace").rstrip())
        return await process.wait()
