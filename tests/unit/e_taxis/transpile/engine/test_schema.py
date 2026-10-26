"""tests/unit/e_taxis/transpile/engine/schema: the grammar parses, compiles to closed msgspec types, and yields leaves."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.models.error import SchemaError

if TYPE_CHECKING:
    from e_taxis.transpile.engine.schema import Schema


@pytest.mark.parametrize(
    ("expr", "value"),
    [
        ("str", "a"),
        ("int", 3),
        ("enum[allow, ask, deny]", "ask"),
        ("list<str>", ["a", "b"]),
        ("map<slot, int>", {"x": 1}),
        ("str | null", None),
        ("enum[grpc, http/protobuf]", "http/protobuf"),
        ("list<entity | 'upstream'>", ["upstream"]),
        ("{a: int, b: list<str>}", {"a": 1}),
    ],
    ids=["scalar", "int", "enum", "list", "map", "nullable", "slash-enum", "literal", "struct-optional"],
)
async def test_schema_validate_accepts(schema: Schema, expr: str, value: Any) -> None:
    schema.declare("entity", schema.parse("str"))
    assert schema.validate(schema.parse(expr), value) is not None or value is None


@pytest.mark.parametrize(
    ("expr", "value"),
    [
        ("int", "3"),
        ("enum[allow, deny]", "ask"),
        ("{a: int}", {"a": 1, "b": 2}),
        ("map<str, int>", {"x": "1"}),
    ],
    ids=["wrong-scalar", "outside-enum", "closed-struct", "map-value"],
)
async def test_schema_validate_refuses(schema: Schema, expr: str, value: Any) -> None:
    with pytest.raises(SchemaError):
        schema.validate(schema.parse(expr), value)


@pytest.mark.parametrize(
    "expr",
    ["<name>", "list<str", "{a int}", "enum[a b]", "str |"],
    ids=["prose", "unclosed", "no-colon", "no-comma", "dangling-union"],
)
async def test_schema_parse_refuses_bad_grammar(schema: Schema, expr: str) -> None:
    with pytest.raises(SchemaError):
        schema.parse(expr)


async def test_schema_compile_refuses_an_undeclared_name(schema: Schema) -> None:
    with pytest.raises(SchemaError, match="declared nowhere"):
        schema.compile(schema.parse("list<Ghost>"))


async def test_schema_struct_keyword_field_keeps_its_wire_name(schema: Schema) -> None:
    row = schema.struct("Row", {"from": {"type": "str"}, "to": {"type": "str", "required": True}})
    built = schema.validate(row, {"from": "a", "to": "b"})
    assert (built.from_, built.to) == ("a", "b")


async def test_schema_struct_required_field_is_enforced(schema: Schema) -> None:
    row = schema.struct("Row", {"to": {"type": "str", "required": True}})
    with pytest.raises(SchemaError, match="to"):
        schema.validate(row, {})


async def test_schema_struct_default_applies(schema: Schema) -> None:
    row = schema.struct("Row", {"glue": {"type": "str", "default": "\n\n"}})
    assert schema.validate(row, {}).glue == "\n\n"


async def test_schema_envelope_leaves_unions(schema: Schema) -> None:
    """Two untagged structs would break msgspec: the resolved envelope is dropped from the union."""
    schema.declare("Node", schema.struct("Node", {"id": "str"}))
    assert schema.validate(schema.parse("list<Node | {source: path}>"), [{"id": "a"}])[0].id == "a"


async def test_schema_leaves_descend_structs_and_star_maps(schema: Schema) -> None:
    schema.declare("Server", schema.struct("Server", {"url": "url", "smoke": "{tool: str}"}))
    node = schema.parse("{servers: map<str, Server>, note: str}")
    assert schema.leaves(node) == {("servers", "*", "url"), ("servers", "*", "smoke", "tool"), ("note",)}


@pytest.mark.parametrize(
    "expr",
    ["str;", ">", "{a: int b: str}", "str >"],
    ids=["unreadable", "unexpected", "struct-separator", "trailing"],
)
async def test_schema_parse_refuses_malformed(schema: Schema, expr: str) -> None:
    with pytest.raises(SchemaError):
        schema.parse(expr)


async def test_schema_field_enum_form_takes_its_values(schema: Schema) -> None:
    row = schema.struct("Row", {"status": {"type": "enum", "values": ["ready", "pending"], "default": "ready"}})
    assert schema.validate(row, {}).status == "ready"
    with pytest.raises(SchemaError):
        schema.validate(row, {"status": "gone"})


async def test_schema_field_refuses_a_spec_without_type(schema: Schema) -> None:
    with pytest.raises(SchemaError, match="type string or a mapping"):
        schema.struct("Row", {"to": 3})


async def test_schema_leaves_stop_at_a_recursive_reference(schema: Schema) -> None:
    schema.declare("Tree", schema.parse("{name: str, child: Tree}"))
    assert schema.leaves(schema.parse("Tree")) == {("name",), ("child",)}


async def test_schema_leaves_of_an_envelope_is_one_leaf(schema: Schema) -> None:
    assert schema.leaves(schema.parse("{body: {source: path}}")) == {("body",)}
