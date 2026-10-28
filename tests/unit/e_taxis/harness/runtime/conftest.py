"""tests/unit/e_taxis/runtime: a workspace as a shell meets it — an e-nous checkout and, beside it, another repo."""

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_resources import Resources


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Resolved, as the locator hands its paths out: macOS's temp dir sits behind the `/var` → `/private/var` link."""
    return tmp_path.resolve() / "ws"


@pytest.fixture
def checkout(resources: Resources, workspace: Path) -> Path:
    """The transpiler's mini e-nous, copied to `ws/e-nous`: a valid checkout (core/schema.yaml, specs/base.yaml)."""
    root = workspace / "e-nous"
    shutil.copytree(resources.path / "transpile", root)
    return root


@pytest.fixture
def sibling(workspace: Path) -> Path:
    """`ws/e-arkhetypo`, a git repo beside the checkout, entered at a nested directory."""
    root = workspace / "e-arkhetypo"
    (root / ".git").mkdir(parents=True)
    (nested := root / "projects" / "python").mkdir(parents=True)
    return nested
