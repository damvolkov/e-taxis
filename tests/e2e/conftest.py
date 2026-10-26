"""tests/e2e: the real thing — a real landrun fence, real harness binaries, a real fake model; slow, never in CI.

Each phantom runs on the fixture checkout copied per test. Before and after the session, the live files a harness
keeps under the real HOME are fingerprinted: a trial that changed one leaked, and fails. `TAXIS_E2E_PATH` prepends
directories to the phantoms' PATH (a pinned harness release beside the installed one)."""

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from e_taxis.transpile.adapters.capture import HttpCapture
from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService

if TYPE_CHECKING:
    from collections.abc import Iterator

##### DEFAULTS #####
LANDRUN = Path("~/.local/bin/landrun").expanduser()
WATCHED = (
    ".claude/CLAUDE.md",
    ".claude/settings.json",
    ".claude.json",
    ".config/opencode/AGENTS.md",
    ".config/opencode/opencode.jsonc",
)


@pytest.fixture(scope="session", autouse=True)
def leak() -> Iterator[None]:
    """The live files under the real HOME, fingerprinted around the whole session."""

    def prints() -> dict[str, str]:
        home = Path.home()
        return {
            name: hashlib.sha256((home / name).read_bytes()).hexdigest() for name in WATCHED if (home / name).is_file()
        }

    before = prints()
    yield
    assert prints() == before, "a trial wrote into the real HOME"


@pytest.fixture
def phantom_path() -> str:
    extra = os.environ.get("TAXIS_E2E_PATH", "")
    return os.pathsep.join(part for part in (extra, os.environ.get("PATH", "")) if part)


@pytest.fixture
def prover(phantom_path: str) -> TrialService:
    match LANDRUN.is_file():
        case False:
            pytest.skip("landrun is not installed")
        case _:
            return TrialService(RunService(CheckService()), LandrunFence(LANDRUN), path=phantom_path)


@pytest.fixture
def nous_root(tmp_path: Path) -> Path:
    root = tmp_path / "nous"
    shutil.copytree(Path(__file__).resolve().parents[1] / "resources" / "transpile", root)
    return root


@pytest.fixture
def capture() -> HttpCapture:
    return HttpCapture()
