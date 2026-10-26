"""tests/unit/e_taxis/transpile/engine: a fresh type namespace per test."""

import pytest

from e_taxis.transpile.engine.schema import Schema


@pytest.fixture
def schema() -> Schema:
    return Schema()
