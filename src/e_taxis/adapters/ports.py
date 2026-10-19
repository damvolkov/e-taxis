"""adapters.ports: what the e-taxis services may ask of the world — the catalog, a source of wanted parts, a core
and its projection per harness, a probe; and on the writing side a command runner, a downloader, one primitive
per installer, the journal's two ends.

Structural contracts only: an adapter satisfies its port by shape. A new source (another harness's
registry), another probe (a container exec), another primitive or another harness's projection is a new
adapter, never an edited service."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.models.brain import BrainRender
    from e_taxis.models.catalog import Catalog, CatalogEntry, CatalogRecipe, Target
    from e_taxis.models.core import Core
    from e_taxis.models.journal import JournalEffect
    from e_taxis.models.plan import Probe
    from e_taxis.models.primitive import PrimitiveContext, PrimitiveResult
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
class CorePort(Protocol):
    """One read of an e-engineer core into the content contract; a CoreError when it cannot be read."""

    async def load(self) -> Core: ...


@runtime_checkable
class HarnessPort(Protocol):
    """A core projected for one harness, landing in `tree`. Pure: nothing is read or written."""

    def render(self, core: Core, tree: Path) -> BrainRender: ...


@runtime_checkable
class ProbePort(Protocol):
    """Run one read-only shell command and report what it found: exit code, first line of output."""

    async def run(self, command: str) -> Probe: ...


@runtime_checkable
class RunnerPort(Protocol):
    """Run one argv, no shell: its output on exit 0, a RunnerError otherwise."""

    async def run(self, argv: tuple[str, ...]) -> str: ...


@runtime_checkable
class DownloaderPort(Protocol):
    """Fetch a URL into `dest`, following redirects; a DownloadError on any failure. Checking it is the caller's."""

    async def fetch(self, url: str, dest: Path) -> None: ...


@runtime_checkable
class PrimitivePort(Protocol):
    """One installer. Each call answers what it changed, so the journal can undo it; a PrimitiveError carries
    whatever it had changed before failing."""

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveResult: ...

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveResult: ...


@runtime_checkable
class RecorderPort(Protocol):
    """The journal's writing end: effects recorded here are filed with the run."""

    def record(self, *effects: JournalEffect) -> None: ...


@runtime_checkable
class UndoPort(Protocol):
    """The journal's reverting end: put one recorded effect back."""

    async def run(self, effect: JournalEffect) -> None: ...
