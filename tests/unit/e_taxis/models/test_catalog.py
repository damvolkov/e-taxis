"""tests/unit/e_taxis/models/catalog: the entry schema — enums decoded, unknown fields refused, applicability, gates."""

from datetime import date
from typing import Any

import msgspec
import pytest

from e_taxis.models.catalog import CatalogEntry, CatalogGate, Kind, Primitive, RecipeKey, Rollout, Target


def test_catalog_entry_decodes_the_schema(alpha: dict[str, Any]) -> None:
    entry = msgspec.convert(alpha, CatalogEntry)
    assert (entry.kind, entry.targets) == (Kind.CLI, (Target.SYSTEM,))
    assert entry.recipes[RecipeKey.ANY].primitive is Primitive.UV_TOOL
    assert entry.recipes[RecipeKey.ANY].with_ == {"source": "alpha"}
    assert entry.status.profile == {"house": Rollout.FLOOR, "minimal": Rollout.OUT}
    assert entry.status.checked == date(2026, 10, 15)
    assert (entry.requires, entry.owns, entry.gate.needed) == ((), (), False)


@pytest.mark.parametrize(
    "change",
    [{"colour": "blue"}, {"kind": "widget"}, {"recipes": {"elsewhere": {"primitive": "npm"}}}],
    ids=["unknown-field", "unknown-kind", "unknown-recipe-key"],
)
def test_catalog_entry_refuses_off_schema(alpha: dict[str, Any], change: dict[str, Any]) -> None:
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(alpha | change, CatalogEntry)


@pytest.mark.parametrize(
    ("targets", "target", "expected"),
    [
        (["system"], Target.CLAUDECODE, True),
        (["opencode"], Target.CLAUDECODE, False),
        (["opencode"], Target.OPENCODE, True),
    ],
    ids=["system-serves-all", "other-harness", "own-harness"],
)
def test_catalog_entry_serves(alpha: dict[str, Any], targets: list[str], target: Target, expected: bool) -> None:
    assert msgspec.convert(alpha | {"targets": targets}, CatalogEntry).serves(target) is expected


@pytest.mark.parametrize(
    ("gate", "expected"),
    [({}, False), ({"licence": "Elastic-2.0"}, True), ({"secrets": ["TOKEN"]}, True), ({"confirm": True}, True)],
    ids=["open", "licence", "secrets", "confirm"],
)
def test_catalog_gate_needed(gate: dict[str, Any], expected: bool) -> None:
    assert msgspec.convert(gate, CatalogGate).needed is expected
