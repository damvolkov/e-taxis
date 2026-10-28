"""tests/unit/e_taxis/workflow/engine: the subjects of the mini e-nous checkout, and plane graphs built by hand."""

from typing import TYPE_CHECKING

import msgspec
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.subject import NousSubject
from e_taxis.workflow.models.workflow import Workflow

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
async def subjects(plane_nous: Path) -> NousSubject:
    return NousSubject(await GitNous(plane_nous, None).load())


@pytest.fixture
def declare() -> Callable[..., Workflow]:
    """A workflow declaration from its nodes as plain mappings, the way a manifest reads."""
    return lambda nodes, **rest: msgspec.convert(
        {"id": "w", "description": "Draw it: the rest is detail.", "domains": ["tekton"], "nodes": nodes, **rest},
        Workflow,
    )
