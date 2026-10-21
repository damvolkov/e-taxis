"""tests/unit/e_taxis/runtime/source: the flags name exactly one source, and the wanted parts are that source's."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import SourceError
from e_taxis.harness.models.ports import SourcePort
from e_taxis.harness.runtime.source import FlagSource

if TYPE_CHECKING:
    from pathlib import Path


async def test_source_profile_flag_reads_the_profile(catalog_root: Path) -> None:
    source = FlagSource(catalog_root, profile="house", nous=None)
    assert isinstance(source, SourcePort)
    assert (await source.wanted(Target.CLAUDECODE))[0].source == "profile:house"


async def test_source_nous_flag_reads_the_checkout(catalog_root: Path, nous_root: Path) -> None:
    wanted = await FlagSource(catalog_root, profile=None, nous=nous_root).wanted(Target.OPENHUMAN)
    assert [part.id for part in wanted] == ["nomad"]


@pytest.mark.parametrize(("profile", "nous"), [(None, None), ("house", "x")], ids=["neither", "both"])
def test_source_refuses_anything_but_one_source(catalog_root: Path, profile: str | None, nous: str | None) -> None:
    with pytest.raises(SourceError, match="exactly one source"):
        FlagSource(catalog_root, profile=profile, nous=None if nous is None else catalog_root / nous)
