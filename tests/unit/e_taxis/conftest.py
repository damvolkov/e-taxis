"""tests/unit/e_taxis: the harness — a real `taxis` per test on its own sqlite file, an in-memory StorePort, the fixture trees.

Safety first: every test runs with HOME and CLAUDE_CONFIG_DIR inside its own temp dir, and every `taxis` run
gets a runner and a downloader that touch nothing — the real ones are tested on their own, on harmless input."""

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

import anyio
import pytest

from e_taxis.cli import build
from e_taxis.harness.models.error import DownloadError, RunnerError
from e_taxis.harness.models.ports import DownloaderPort, RunnerPort
from e_taxis.harness.runtime.deps import Deps

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from pytest_resources import Resources

    from e_taxis.harness.models.journal import JournalEffect


class MemoryStore:
    """StorePort over a dict: the services and the journal are tested against the port, not against sqlite."""

    name: ClassVar[str] = "memory"

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def set(self, key: str, value: bytes) -> None:
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def keys(self, prefix: str = "") -> AsyncIterator[str]:
        for key in sorted(self.data):
            if key.startswith(prefix):
                yield key


class ListUndo:
    """UndoPort over a list: every effect it was asked to revert, in order; one in `failing` raises."""

    def __init__(self) -> None:
        self.reverted: list[JournalEffect] = []
        self.failing: list[JournalEffect] = []
        self.oserror = False

    async def run(self, effect: JournalEffect) -> None:
        if effect in self.failing and self.oserror:
            raise PermissionError(13, "Permission denied", "/x")
        if effect in self.failing:
            msg = f"cannot revert {effect}"
            raise RunnerError(msg)
        self.reverted.append(effect)


class FakeRunner:
    """RunnerPort that runs nothing: every argv is recorded; one starting with a prefix in `failing` fails."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.failing: set[tuple[str, ...]] = set()

    async def run(self, argv: tuple[str, ...]) -> str:
        self.calls.append(argv)
        if any(argv[: len(prefix)] == prefix for prefix in self.failing):
            msg = f"`{' '.join(argv)}` exited 1"
            raise RunnerError(msg)
        return ""


class FakeDownloader:
    """DownloaderPort over a dict url → bytes: an unknown url is a 404."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def fetch(self, url: str, dest: Path) -> None:
        if url not in self.blobs:
            msg = f"{url}: 404"
            raise DownloadError(msg)
        await anyio.Path(dest).write_bytes(self.blobs[url])


@pytest.fixture(autouse=True)
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test runs in its own directory: the default relative DB_PATH lands in it, never in the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME and CLAUDE_CONFIG_DIR inside the test's temp dir: nothing a test runs can reach the real ones."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.delenv("TAXIS_NPM_PREFIX", raising=False)
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    return tmp_path / "claude"


@pytest.fixture
def undoer() -> ListUndo:
    return ListUndo()


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def downloader() -> FakeDownloader:
    return FakeDownloader()


@pytest.fixture(autouse=True)
def sandbox(monkeypatch: pytest.MonkeyPatch, runner: FakeRunner, downloader: FakeDownloader) -> None:
    """Every `taxis` run builds the fake runner and downloader in place of the real ones."""

    async def fake_runner(deps: Deps) -> FakeRunner:
        return runner

    async def fake_downloader(deps: Deps) -> FakeDownloader:
        return downloader

    providers = {**Deps.PROVIDERS, RunnerPort: fake_runner, DownloaderPort: fake_downloader}
    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType(providers))


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def taxis(capfd: pytest.CaptureFixture[str]) -> Callable[..., tuple[int, str, str]]:
    """Run the real app on a token list: (exit code, stdout, stderr), exactly what a shell would see."""

    def run(*tokens: str) -> tuple[int, str, str]:
        capfd.readouterr()
        code = build().meta(list(tokens))
        out, err = capfd.readouterr()
        return code or 0, out, err

    return run


@pytest.fixture
def catalog_root(resources: Resources) -> Path:
    """A sound catalog: five entries, one profile — `house` wants a part the catalog does not know."""
    return resources.path / "catalog"


@pytest.fixture
def doctor_root(resources: Resources) -> Path:
    """A broken catalog: unparsable and off-schema files, a duplicate id, a dangling require, a cycle, a clash."""
    return resources.path / "doctor"


@pytest.fixture
def nous_root(resources: Resources) -> Path:
    """A fake e-nous checkout: `core/common/stack.yaml` plus two facet stacks."""
    return resources.path / "nous"


@pytest.fixture
def broken_root(resources: Resources) -> Path:
    """An e-nous checkout whose registry is off-schema."""
    return resources.path / "broken"


@pytest.fixture
def cycle_root(resources: Resources) -> Path:
    """A catalog whose two entries require each other."""
    return resources.path / "cycle"


@pytest.fixture
def world_root(resources: Resources) -> Path:
    """A catalog that writes: uv-tool, settings, file, claude-mcp and npm parts, a skip, a deferral, a gate."""
    return resources.path / "world"


@pytest.fixture
def dangling_root(resources: Resources) -> Path:
    """A catalog whose one entry requires an id no entry provides."""
    return resources.path / "dangling"
