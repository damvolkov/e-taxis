"""adapters.ports: what the e-taxis services may ask of the world — the catalog, a source of wanted parts, a probe.

Structural contracts only: an adapter satisfies its port by shape. A new source (another harness's
registry) or another probe (a container exec) is a new adapter, never an edited service."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from e_taxis.models.catalog import Catalog, Target
    from e_taxis.models.plan import Probe
    from e_taxis.models.wanted import WantedPart


##### TYPES #####
@runtime_checkable
class CatalogPort(Protocol):
    """Every catalog entry, loaded at once: a broken file is reported in the result, never raised."""

    async def load(self) -> Catalog: ...


@runtime_checkable
class SourcePort(Protocol):
    """The parts one target wants, in the order the source lists them."""

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]: ...


@runtime_checkable
class ProbePort(Protocol):
    """Run one read-only shell command and report what it found: exit code, first line of output."""

    async def run(self, command: str) -> Probe: ...
