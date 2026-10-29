"""tests/unit/e_taxis/workflow/commands: checkouts in the state a promotion meets — an enhancement with a patch, and the
same with HEAD moved past its base; and soa-assess's world for `taxis` — the recorded API and the stand-in lab in
place of the real ones, a soa.yaml in the checkout, the soa state dir and the live trees under the test's temp dir."""

import shutil
from types import MappingProxyType
from typing import TYPE_CHECKING

import pytest

from e_taxis.harness.runtime.deps import Deps
from e_taxis.workflow.models.ports import ApiPort, LabPort

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from pytest_resources import Resources

    from e_taxis.workflow.models.ports import ApiPort as Api
    from e_taxis.workflow.models.ports import LabPort as Lab
    from e_taxis.workflow.services.plane import PlaneRun

LIB = "core/tekton/skills/algo-py-core/references/lib.md"


@pytest.fixture
def enhanced(taxis: Callable[..., tuple[int, str, str]], plane_nous: Path, plane_deps: PlaneRun) -> Path:
    """An enhancement of the mini checkout's skill over a hand edit, the edit then undone: a patch to promote. At the
    commit cadence the weekly measures idle, so the verdict is `propose` — promotable by id or with every verdict."""
    lib = plane_nous / LIB
    original = lib.read_text()
    lib.write_text(original + "\nPromoted depth.\n")
    code, _, _ = taxis(
        "enhance", "run", "skill", "algo-py-core", "--nous", str(plane_nous), "--manual", "--cadence", "commit"
    )
    lib.write_text(original)
    assert code == 0
    return plane_nous


@pytest.fixture
async def moved(enhanced: Path, tree, commit: Callable[..., Awaitable[str]]) -> Path:
    """The enhanced checkout with one commit past the run's base."""
    tree(enhanced, {"NEW.md": "moved\n"})
    await commit(enhanced, "moved")
    return enhanced


@pytest.fixture
def assess_world(
    monkeypatch: pytest.MonkeyPatch, api: Api, lab: Lab, nous: Path, resources: Resources, tmp_path: Path
) -> Path:
    """Every `taxis` run reads the recorded API and benches through the stand-in lab; returns the soa state dir."""

    async def apis(deps: Deps) -> Api:
        return api

    async def labs(deps: Deps) -> Lab:
        return lab

    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, ApiPort: apis, LabPort: labs}))
    shutil.copy(
        resources.path / "assess" / "nous" / "core" / "tekton" / "config" / "soa.yaml",
        nous / "core" / "tekton" / "config",
    )
    monkeypatch.setenv("TAXIS_SOA_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("TAXIS_WORKFLOW_OPENCODE", str(resources.path / "assess" / "trees" / "opencode"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(resources.path / "assess" / "trees" / "claude"))
    return tmp_path / "state"
