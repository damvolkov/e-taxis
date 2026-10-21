"""tests/unit/e_taxis/adapters/source: what is wanted — a shipped profile, or an e-nous checkout's stack registry."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.source import NousSource, ProfileSource
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.error import CatalogError, SourceError
from e_taxis.harness.models.ports import SourcePort

if TYPE_CHECKING:
    from pathlib import Path


def test_source_adapters_satisfy_the_port(catalog_root: Path, nous_root: Path) -> None:
    assert isinstance(ProfileSource(catalog_root, "house"), SourcePort)
    assert isinstance(NousSource(nous_root), SourcePort)


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
                ("beta", None, "tekton"),
                ("ghost", None, "tekton"),
            ],
        ),
        (Target.OPENCODE, [("alpha", "v1.2.3", "common"), ("gamma", None, "tekton")]),
        (Target.OPENHUMAN, [("nomad", None, "nomos")]),
    ],
    ids=["claudecode", "opencode", "openhuman"],
)
async def test_nous_wanted_keeps_the_parts_the_backend_uses(
    nous_root: Path, target: Target, expected: list[tuple[str, str | None, str]]
) -> None:
    wanted = await NousSource(nous_root).wanted(target)
    assert [(part.id, part.pin, part.source) for part in wanted] == [
        (part, pin, f"nous:core/{facet}/stack.yaml") for part, pin, facet in expected
    ]


async def test_nous_wanted_outside_a_checkout_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not an e-nous checkout"):
        await NousSource(tmp_path).wanted(Target.CLAUDECODE)


async def test_nous_wanted_off_schema_registry_is_refused(broken_root: Path) -> None:
    with pytest.raises(SourceError, match=r"core/common/stack\.yaml"):
        await NousSource(broken_root).wanted(Target.CLAUDECODE)
