"""tests/unit/e_taxis/transpile: a small e-nous checkout copied per test, read through the real adapter.

`tests/resources/transpile` holds the two schemas, the four specs, the whole persona and config of both facets and one
instance of each entity, copied from e-nous: the law must find nothing blocking in it. `edit` rewrites one YAML
file of the copy in place, so a test states only the mutation it makes."""

import shutil
from typing import TYPE_CHECKING, Any

import anyio
import eserde
import pytest
import yaml

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.engine.model import CoreModel, SpecModel

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_resources import Resources

    from e_taxis.transpile.models.nous import NousTree


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


@pytest.fixture
async def nous_tree(nous_root: Path) -> NousTree:
    return await GitNous(nous_root, None).load()


@pytest.fixture
def core_model(nous_tree: NousTree) -> CoreModel:
    return CoreModel(nous_tree.schema)


@pytest.fixture
def spec_model(nous_tree: NousTree) -> SpecModel:
    return SpecModel(nous_tree.base)
