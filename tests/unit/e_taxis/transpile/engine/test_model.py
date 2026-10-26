"""tests/unit/e_taxis/transpile/engine/model: both schemas of the checkout compiled on the fly, and held to."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.engine.model import CoreModel, SpecModel
from e_taxis.transpile.models.error import SchemaError
from e_taxis.transpile.models.report import ReportKind

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree


async def test_model_core_accepts_every_module_of_the_fixture(core_model: CoreModel, nous_tree: NousTree) -> None:
    checked = [
        core_model.check_module(facet, name, value)
        for facet, modules in nous_tree.config.items()
        for name, value in modules.items()
    ]
    assert len(checked) == sum(len(modules) for modules in nous_tree.config.values())


async def test_model_core_accepts_every_instance_of_the_fixture(core_model: CoreModel, nous_tree: NousTree) -> None:
    checked = [
        core_model.check_entity(entity, value)
        for entity, found in nous_tree.entities.items()
        for value in found.values()
    ]
    assert len(checked) == 4


@pytest.mark.parametrize(
    ("facet", "module", "value"),
    [
        ("tekton", "main", {"user": "d", "model": {"default": "b", "small": "s"}, "colour": "red"}),
        ("nomos", "tools", {"steps": "many"}),
        ("tekton", "ghost", {}),
    ],
    ids=["undeclared-key", "wrong-type", "undeclared-module"],
)
async def test_model_core_refuses_a_module(
    core_model: CoreModel, facet: str, module: str, value: dict[str, Any]
) -> None:
    with pytest.raises(SchemaError):
        core_model.check_module(facet, module, value)


async def test_model_core_refuses_an_undeclared_entity_field(core_model: CoreModel, nous_tree: NousTree) -> None:
    with pytest.raises(SchemaError, match="unknown field"):
        core_model.check_entity("skill", {**nous_tree.entities["skill"]["algo-py-core"], "licence": "MIT"})


async def test_model_core_config_leaves_reach_per_item_fields(core_model: CoreModel) -> None:
    assert {("mcp", "servers", "*", "smoke", "tool"), ("main", "model", "alias", "*")} <= core_model.config_leaves(
        "tekton"
    )


async def test_model_spec_accepts_the_four_specs(spec_model: SpecModel, nous_tree: NousTree) -> None:
    assert sorted(spec_model.check(spec).backend for spec in nous_tree.specs.values()) == [
        "claudecode",
        "hermes",
        "opencode",
        "openhuman",
    ]


async def test_model_spec_refuses_an_undeclared_row_field(spec_model: SpecModel, nous_tree: NousTree) -> None:
    spec = nous_tree.specs["tekton/claudecode"]
    rows = [{**spec["map"]["persona"]["rows"][0], "at": 1}]
    broken = {**spec, "map": {**spec["map"], "persona": {**spec["map"]["persona"], "rows": rows}}}
    with pytest.raises(SchemaError, match="at"):
        spec_model.check(broken)


async def test_model_spec_declares_every_kind_the_report_emits(spec_model: SpecModel) -> None:
    assert {kind.value for kind in ReportKind} <= set(spec_model.kinds)


async def test_model_core_refuses_a_module_without_fields_or_shape(nous_tree: NousTree) -> None:
    raw = {**nous_tree.schema, "config": {**nous_tree.schema["config"], "tekton": {"main": {"doc": "nothing"}}}}
    with pytest.raises(SchemaError, match="neither"):
        CoreModel(raw)
