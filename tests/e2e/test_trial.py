"""tests/e2e/trial: each harness raised for real, fenced, on the fixture core — it must show all it was given, run
every hook it was given, and let a hook's exit 2 block where the moment allows it."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import pytest
import yaml

from e_taxis.transpile.adapters.capture import HttpCapture
from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.adapters.nous import GitNous

if TYPE_CHECKING:
    from e_taxis.transpile.services.trial import TrialService

pytestmark = pytest.mark.slow

##### DEFAULTS #####
CC = "specs/tekton/claudecode.yaml"
OC = "specs/tekton/opencode.yaml"


async def test_trial_fence_holds_on_this_kernel(tmp_path: Path) -> None:
    fence = LandrunFence(Path("~/.local/bin/landrun").expanduser())
    assert await fence.canary(tmp_path / "in", tmp_path.parent / f"{tmp_path.name}-outside")


class KeptCapture(HttpCapture):
    """The fake model, keeping every probe's bodies across the clears between probes."""

    __slots__ = ("kept",)

    def __init__(self) -> None:
        super().__init__()
        self.kept: list[bytes] = []

    def clear(self) -> None:
        self.kept.extend(self.bodies())
        super().clear()


async def _skip_without(backend: str, phantom_path: str) -> None:
    binary = shutil.which({"claudecode": "claude"}.get(backend, backend), path=phantom_path)
    version = (
        "" if binary is None else (await anyio.run_process([binary, "--version"], check=False)).stdout.decode().strip()
    )
    match (binary, backend, version.removeprefix("opencode ").startswith("v2.")):
        case (None, _, _):
            pytest.skip(f"no {backend} binary on the PATH")
        case (_, "opencode", False):
            pytest.skip("the spec's opencode trial runs on the pinned 2.x line (stack.yaml); set TAXIS_E2E_PATH to one")
        case _:
            pass


@pytest.mark.parametrize("backend", ["claudecode", "opencode", "hermes"])
async def test_trial_harness_shows_the_render(
    prover: TrialService, capture: HttpCapture, nous_root: Path, phantom_path: str, backend: str
) -> None:
    await _skip_without(backend, phantom_path)
    report = await prover.run(GitNous(nous_root, None), backend, capture)
    assert report.captured >= 1, report.runs
    assert report.held, [(sight.entity, sight.missing) for sight in report.sights]


@pytest.mark.parametrize(("backend", "spec"), [("claudecode", CC), ("opencode", OC)])
async def test_trial_hooks_block_where_the_moment_allows(
    prover: TrialService, nous_root: Path, phantom_path: str, backend: str, spec: str
) -> None:
    await _skip_without(backend, phantom_path)
    hooks = nous_root / "core/tekton/config/hooks.yaml"
    blocking = hooks.read_text().replace(
        'run: [sh, -c, "exit 0", tool_before]', 'run: [sh, -c, "echo denied-by-house >&2; exit 2"]'
    )
    hooks.write_text(blocking)
    path = nous_root / spec
    data = yaml.safe_load(path.read_text())
    data["trial"]["state"] = [
        {"path": "${home}/.plans/TODO_ghost.md", "text": "not a plan"},
        *data["trial"].get("state", []),
    ]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    capture = KeptCapture()
    await prover.run(GitNous(nous_root, None), backend, capture)
    capture.clear()
    said = b"\n".join(capture.kept)
    assert b"plans law (persona: Plans)" in said
    assert b"denied-by-house" in said
