"""tests/e2e/trial: each harness raised for real, fenced, on the fixture core — it must show all it was given."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import pytest

from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.adapters.nous import GitNous

if TYPE_CHECKING:
    from e_taxis.transpile.adapters.capture import HttpCapture
    from e_taxis.transpile.services.trial import TrialService

pytestmark = pytest.mark.slow


async def test_trial_fence_holds_on_this_kernel(tmp_path: Path) -> None:
    fence = LandrunFence(Path("~/.local/bin/landrun").expanduser())
    assert await fence.canary(tmp_path / "in", tmp_path.parent / f"{tmp_path.name}-outside")


@pytest.mark.parametrize("backend", ["claudecode", "opencode", "hermes"])
async def test_trial_harness_shows_the_render(
    prover: TrialService, capture: HttpCapture, nous_root: Path, phantom_path: str, backend: str
) -> None:
    binary = shutil.which({"claudecode": "claude"}.get(backend, backend), path=phantom_path)
    version = (
        "" if binary is None else (await anyio.run_process([binary, "--version"], check=False)).stdout.decode().strip()
    )
    match (binary, backend, version.startswith("1.")):
        case (None, _, _):
            pytest.skip(f"no {backend} binary on the PATH")
        case (_, "opencode", False):
            pytest.skip("the spec's opencode trial runs on the stable 1.x line; set TAXIS_E2E_PATH to one")
        case _:
            pass
    report = await prover.run(GitNous(nous_root, None), backend, capture)
    assert report.captured >= 1, report.runs
    assert report.held, [(sight.entity, sight.missing) for sight in report.sights]
