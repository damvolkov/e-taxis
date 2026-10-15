"""tests/unit/e_taxis/models/profile: a profile names parts and how each rolls out; nothing else."""

from typing import Any

import msgspec
import pytest

from e_taxis.models.catalog import Rollout
from e_taxis.models.profile import Profile


def test_profile_decodes_parts_with_their_rollout(house: dict[str, Any]) -> None:
    profile = msgspec.convert(house, Profile)
    assert profile.id == "house"
    assert profile.parts["gamma"] is Rollout.PER_PROJECT


@pytest.mark.parametrize("change", [{"parts": {"alpha": "sometimes"}}, {"extra": 1}], ids=["rollout", "field"])
def test_profile_refuses_off_schema(house: dict[str, Any], change: dict[str, Any]) -> None:
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(house | change, Profile)
