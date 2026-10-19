"""tests/unit/e_taxis/models/catalog: the entry schema — enums decoded, unknown fields refused, applicability, gates."""

from datetime import date
from typing import Any

import msgspec
import pytest

from e_taxis.models.catalog import (
    CatalogEntry,
    CatalogGate,
    CatalogRecipe,
    Kind,
    Primitive,
    RecipeKey,
    Rollout,
    Target,
)
from e_taxis.models.error import RecipeError
from e_taxis.models.recipe import RecipeUv


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


@pytest.mark.parametrize(
    ("recipes", "target", "expected"),
    [
        ({"any": {"primitive": "npm"}}, Target.CLAUDECODE, Primitive.NPM),
        ({"any": {"primitive": "npm"}, "claudecode": {"primitive": "uv-tool"}}, Target.CLAUDECODE, Primitive.UV_TOOL),
        ({"opencode": {"primitive": "npm"}}, Target.CLAUDECODE, None),
    ],
    ids=["any", "own-target-first", "none"],
)
def test_catalog_entry_recipe(alpha: dict[str, Any], recipes: dict[str, Any], target: Target, expected) -> None:
    recipe = msgspec.convert(alpha | {"recipes": recipes}, CatalogEntry).recipe(target)
    assert (recipe and recipe.primitive) == expected


def test_catalog_recipe_args_converts_and_ignores_annotations() -> None:
    recipe = CatalogRecipe(primitive=Primitive.UV_TOOL, with_={"source": "x@1", "name": "x", "note": "kept out"})
    assert recipe.args(RecipeUv) == RecipeUv(source="x@1", name="x")


def test_catalog_recipe_args_off_schema_is_a_recipe_error() -> None:
    with pytest.raises(RecipeError, match="uv-tool recipe"):
        CatalogRecipe(primitive=Primitive.UV_TOOL, with_={"name": "x"}).args(RecipeUv)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, None),
        ({"scope": "user"}, None),
        ({"scope": "project"}, "deferred: the project scope lands in P3"),
        ({"recipes": {"any": {"primitive": "compose"}}}, "deferred: compose lands in P3"),
    ],
    ids=["machine", "user", "project", "compose"],
)
def test_catalog_entry_deferral(alpha: dict[str, Any], change: dict[str, Any], expected: str | None) -> None:
    assert msgspec.convert(alpha | change, CatalogEntry).deferral(Target.CLAUDECODE) == expected
