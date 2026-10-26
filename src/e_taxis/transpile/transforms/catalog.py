"""transforms.catalog: every backend's transform table, by backend id — the only place the renderer finds them."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.transforms import claudecode, hermes, opencode, openhuman

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.transpile.engine.context import RowContext

##### TABLE #####
CATALOG: Final[Mapping[str, Mapping[str, Callable[[Any, RowContext], Any]]]] = MappingProxyType(
    {
        claudecode.BACKEND: claudecode.TRANSFORMS,
        opencode.BACKEND: opencode.TRANSFORMS,
        hermes.BACKEND: hermes.TRANSFORMS,
        openhuman.BACKEND: openhuman.TRANSFORMS,
    }
)
