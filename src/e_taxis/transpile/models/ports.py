"""models.ports: what the transpiler asks of the world — one read of an e-nous checkout, a fence, a fake model."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree
from e_taxis.transpile.models.trial import TrialRun


##### TYPES #####
@runtime_checkable
class NousPort(Protocol):
    """One read of a checkout: schemas, specs and core, envelopes resolved; a NousError when it cannot be read."""

    async def load(self) -> NousTree: ...


@runtime_checkable
class FencePort(Protocol):
    """Runs argv confined: read and execute everywhere, write only under `writable`, connect only to `ports`."""

    async def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        writable: Sequence[Path],
        ports: Sequence[int],
        limit: float,
    ) -> TrialRun: ...

    async def canary(self, inside: Path, outside: Path) -> bool: ...

    def serve(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        writable: Sequence[Path],
        ports: Sequence[int],
        binds: Sequence[int],
    ) -> AbstractAsyncContextManager[None]: ...


@runtime_checkable
class CapturePort(Protocol):
    """A fake model endpoint: where a phantom sends its calls, and every request body it received."""

    @property
    def url(self) -> str: ...

    @property
    def port(self) -> int: ...

    def bodies(self) -> tuple[bytes, ...]: ...

    def clear(self) -> None: ...

    def serve(self) -> AbstractAsyncContextManager[CapturePort]: ...
