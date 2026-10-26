"""models.ports: what the transpiler asks of the world — today, one read of an e-nous checkout."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree


##### TYPES #####
@runtime_checkable
class NousPort(Protocol):
    """One read of a checkout: schemas, specs and core, envelopes resolved; a NousError when it cannot be read."""

    async def load(self) -> NousTree: ...
