"""runtime.source: the source a command's flags name — `--profile NAME` or `--nous PATH`, exactly one.

Choosing between adapters is wiring, so it lives in the runtime beside `Deps`, not in a command or a service."""

from pathlib import Path

from e_taxis.adapters.source import NousSource, ProfileSource
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import SourceError
from e_taxis.harness.models.ports import SourcePort
from e_taxis.harness.models.wanted import WantedPart


##### TYPES #####
class FlagSource:
    """Satisfies SourcePort by delegating to the one adapter the flags select; refuses none or both at once."""

    __slots__ = ("_inner",)

    def __init__(self, catalog: Path, *, profile: str | None, nous: Path | None) -> None:
        self._inner: SourcePort
        match (profile, nous):
            case (str() as name, None):
                self._inner = ProfileSource(catalog, name)
            case (None, Path() as root):
                self._inner = NousSource(root)
            case _:
                msg = "pass exactly one source: --profile NAME or --nous PATH"
                raise SourceError(msg)

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]:
        return await self._inner.wanted(target)
