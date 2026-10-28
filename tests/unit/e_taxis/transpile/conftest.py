"""tests/unit/e_taxis/transpile: a small e-nous checkout copied per test, read through the real adapter.

`tests/resources/transpile` holds the two schemas, the four specs, the whole persona and config of both facets and one
instance of each entity, copied from e-nous: the law must find nothing blocking in it. `edit` rewrites one YAML
file of the copy in place, so a test states only the mutation it makes."""

import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import eserde
import pytest
import yaml

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.engine.context import RowContext
from e_taxis.transpile.engine.model import CoreModel, SpecModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from pytest_resources import Resources

    from e_taxis.transpile.models.nous import NousTree
from e_taxis.transpile.models.trial import TrialRun


@pytest.fixture
def nous_root(resources: Resources, tmp_path: Path) -> Path:
    root = tmp_path / "nous"
    shutil.copytree(resources.path / "transpile", root)
    return root


@pytest.fixture
async def nous_git(nous_root: Path) -> Path:
    """The copy as a git checkout with one commit."""
    git = ("git", "-C", str(nous_root), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false")
    _ = [await anyio.run_process((*git, *args)) for args in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "nous"))]
    return nous_root


@pytest.fixture
def edit(nous_root: Path) -> Callable[[str, Callable[[Any], None]], None]:
    """Load one YAML file of the copy, let the test change it, write it back."""

    def apply(relative: str, change: Callable[[Any], None]) -> None:
        path = nous_root / relative
        data = eserde.load(path)
        change(data)
        ### PyYAML writes it back: e-serde 0.5.1 dumps a list of lists with a broken indent (`-     - a`).
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    return apply


class FakeCapture:
    """CapturePort in memory: a test (or the fake fence) appends the bodies a harness would have sent."""

    def __init__(self) -> None:
        self.received: list[bytes] = []
        self.served = 0

    @property
    def url(self) -> str:
        return "http://127.0.0.1:1"

    @property
    def port(self) -> int:
        return 1

    def bodies(self) -> tuple[bytes, ...]:
        return tuple(self.received)

    def clear(self) -> None:
        self.received.clear()

    @asynccontextmanager
    async def serve(self) -> AsyncIterator[FakeCapture]:
        self.served += 1
        yield self


class FakeFence:
    """FencePort that raises no harness: each run 'sends' `body` to the capture and prints `stdout`; `holds` is the canary."""

    def __init__(self, capture: FakeCapture) -> None:
        self.capture = capture
        self.body = b""
        self.stdout = ""
        self.holds = True
        self.argvs: list[tuple[str, ...]] = []
        self.envs: list[dict[str, str]] = []
        self.served: list[tuple[str, ...]] = []
        self.codes: list[int] = []

    async def run(self, argv, *, env, cwd, writable, ports, limit) -> TrialRun:
        self.argvs.append(tuple(argv))
        self.envs.append(dict(env))
        self.capture.received.append(self.body)
        code = self.codes.pop(0) if self.codes else 1
        return TrialRun(argv=tuple(argv), code=code, seconds=0.0, stdout=self.stdout)

    async def canary(self, inside: Path, outside: Path) -> bool:
        return self.holds

    @asynccontextmanager
    async def serve(self, argv, *, env, cwd, writable, ports, binds) -> AsyncIterator[None]:
        self.served.append(tuple(argv))
        yield


class ListRecorder:
    """RecorderPort over a list: every effect a landing recorded, in order."""

    def __init__(self) -> None:
        self.effects: list[Any] = []

    def record(self, *effects: Any) -> None:
        self.effects.extend(effects)


@pytest.fixture
def recorder() -> ListRecorder:
    return ListRecorder()


@pytest.fixture
def capture() -> FakeCapture:
    return FakeCapture()


@pytest.fixture
def fence(capture: FakeCapture) -> FakeFence:
    return FakeFence(capture)


@pytest.fixture
def landrun(resources: Resources) -> Path:
    """A stand-in landrun: drops the fence flags and runs the command, so the fence adapter runs in CI."""
    return resources.path / "landrun" / "landrun"


@pytest.fixture
def golden_root() -> Path:
    """The v1 transpiler's render of every backend into empty trees (`backup/e-nous/golden`): the acceptance bar."""
    return Path(__file__).resolve().parents[4] / "backup" / "e-nous" / "golden"


@pytest.fixture
def ctx(nous_tree: NousTree) -> RowContext:
    """The tekton facet's config, claudecode's natives, `{out}` bound to /out."""
    return RowContext(
        config=nous_tree.config["tekton"], native={"names": {"alibaba": "nomos-alibaba"}}, bindings={"out": "/out"}
    )


@pytest.fixture
async def nous_tree(nous_root: Path) -> NousTree:
    return await GitNous(nous_root, None).load()


@pytest.fixture
def core_model(nous_tree: NousTree) -> CoreModel:
    return CoreModel(nous_tree.schema)


@pytest.fixture
def spec_model(nous_tree: NousTree) -> SpecModel:
    return SpecModel(nous_tree.base)


@pytest.fixture
def without_added() -> Callable[[bytes], bytes]:
    """A persona render with the sections v2 added on purpose cut out: what is left must be v1's, byte for byte."""
    added = re.compile(rb"\n\n## (Plans|Agents)\n.*?(?=\n\n## |\Z)", re.DOTALL)
    return lambda text: added.sub(b"", text)
