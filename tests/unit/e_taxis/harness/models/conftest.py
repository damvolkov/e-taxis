"""tests/unit/e_taxis/models: catalog fixtures as the YAML parser hands them over — plain dicts, not yet typed."""

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytest_resources import Resources


@pytest.fixture
def alpha(resources: Resources) -> dict[str, Any]:
    return dict(resources.catalog.entries.alpha)


@pytest.fixture
def house(resources: Resources) -> dict[str, Any]:
    return dict(resources.catalog.profiles.house)
