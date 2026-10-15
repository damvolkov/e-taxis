"""tests/unit/e_taxis/adapters/source: what is wanted — a shipped profile, or an e-engineer checkout's stack registry."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.ports import SourcePort
from e_taxis.adapters.source import EngineerSource, ProfileSource
from e_taxis.models.catalog import Target
from e_taxis.models.error import CatalogError, SourceError

if TYPE_CHECKING:
    from pathlib import Path


def test_source_adapters_satisfy_the_port(catalog_root: Path, engineer_root: Path) -> None:
    assert isinstance(ProfileSource(catalog_root, "house"), SourcePort)
    assert isinstance(EngineerSource(engineer_root), SourcePort)


async def test_profile_wanted_skips_what_the_profile_leaves_out(catalog_root: Path) -> None:
    wanted = await ProfileSource(catalog_root, "house").wanted(Target.CLAUDECODE)
    assert [part.id for part in wanted] == ["alpha", "beta", "gamma", "delta", "ghost"]
    assert {(part.source, part.pin) for part in wanted} == {("profile:house", None)}


async def test_profile_wanted_unknown_profile_lists_the_shipped_ones(catalog_root: Path) -> None:
    with pytest.raises(SourceError, match=r"no profile 'nope'.*house"):
        await ProfileSource(catalog_root, "nope").wanted(Target.CLAUDECODE)


async def test_profile_wanted_off_schema_profile_is_a_catalog_error(doctor_root: Path) -> None:
    with pytest.raises(CatalogError, match=r"bad\.yaml"):
        await ProfileSource(doctor_root, "bad").wanted(Target.CLAUDECODE)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (
            Target.CLAUDECODE,
            [
                ("alpha", "v1.2.3", "common"),
                ("epsilon", "9.9", "common"),
                ("beta", None, "engineer"),
                ("ghost", None, "engineer"),
            ],
        ),
        (Target.OPENCODE, [("alpha", "v1.2.3", "common"), ("gamma", None, "engineer")]),
        (Target.OPENHUMAN, [("nomad", None, "nomos")]),
    ],
    ids=["claudecode", "opencode", "openhuman"],
)
async def test_engineer_wanted_keeps_the_parts_the_backend_uses(
    engineer_root: Path, target: Target, expected: list[tuple[str, str | None, str]]
) -> None:
    wanted = await EngineerSource(engineer_root).wanted(target)
    assert [(part.id, part.pin, part.source) for part in wanted] == [
        (part, pin, f"engineer:core/{facet}/stack.yaml") for part, pin, facet in expected
    ]


async def test_engineer_wanted_outside_a_checkout_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not an e-engineer checkout"):
        await EngineerSource(tmp_path).wanted(Target.CLAUDECODE)


async def test_engineer_wanted_off_schema_registry_is_refused(broken_root: Path) -> None:
    with pytest.raises(SourceError, match=r"core/common/stack\.yaml"):
        await EngineerSource(broken_root).wanted(Target.CLAUDECODE)
