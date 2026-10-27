"""tests/unit/e_taxis/workflow/engine: the subjects of the mini e-nous checkout, and plane graphs built by hand."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.subject import NousSubject

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
async def subjects(plane_nous: Path) -> NousSubject:
    return NousSubject(await GitNous(plane_nous, None).load())
