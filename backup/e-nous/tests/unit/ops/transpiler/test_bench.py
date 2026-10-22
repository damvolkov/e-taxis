"""Unit tests for the bench: every gate holds for every backend, on throwaway destinations."""

from __future__ import annotations

from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.entity import BACKENDS, Backend, Harness
from ops.transpiler.bench import Bench
from ops.transpiler.render import Transpiler


@pytest.mark.parametrize("backend", BACKENDS[Harness.TEKTON], ids=str)
def test_capability_prunes_an_orphan_of_a_tree_the_backend_governs(tmp_path: Path, backend: Backend) -> None:
    gate = Bench(backend).capability(tmp_path / "capability")
    assert gate.passed, gate.detail


@pytest.mark.parametrize("backend", list(Backend), ids=str)
def test_fidelity_judges_the_backends_own_tree(tmp_path: Path, backend: Backend) -> None:
    """Every backend owns a live tree; fidelity is never another backend's question."""
    assert Bench(backend).out == settings.transpiler.live(backend)
    Transpiler(backend=backend, out=tmp_path).export()
    gate = Bench(backend, out=tmp_path).fidelity()
    assert gate.passed, gate.detail
