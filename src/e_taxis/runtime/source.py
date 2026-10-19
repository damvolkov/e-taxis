"""runtime.source: the source a command's flags name — `--profile NAME` or `--engineer PATH`, exactly one.

Choosing between adapters is wiring, so it lives in the runtime beside `Deps`, not in a command or a service."""

from pathlib import Path

from e_taxis.adapters.ports import SourcePort
from e_taxis.adapters.source import EngineerSource, ProfileSource
from e_taxis.models.catalog import Target
from e_taxis.models.error import SourceError
from e_taxis.models.wanted import WantedPart


##### TYPES #####
class FlagSource:
    """Satisfies SourcePort by delegating to the one adapter the flags select; refuses none or both at once."""

    __slots__ = ("_inner",)

    def __init__(self, catalog: Path, *, profile: str | None, engineer: Path | None) -> None:
        self._inner: SourcePort
        match (profile, engineer):
            case (str() as name, None):
                self._inner = ProfileSource(catalog, name)
            case (None, Path() as root):
                self._inner = EngineerSource(root)
            case _:
                msg = "pass exactly one source: --profile NAME or --engineer PATH"
                raise SourceError(msg)

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]:
        return await self._inner.wanted(target)
