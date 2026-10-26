"""engine.schema: a type grammar read from data, compiled on the fly — the only models the transpiler has.

e-nous declares its two shapes as YAML: `core/schema.yaml` (what the core may hold) and `specs/base.yaml · kinds`
(what a spec may say). Neither has a hand-written twin here. Each type expression is parsed once into an AST and
compiled to msgspec types (`msgspec.defstruct`, closed: an undeclared field is an error), and the same AST yields
the leaf paths the coverage law walks.

    expr  := term ('|' term)*
    term  := 'list<' expr '>' | 'map<' expr ',' expr '>' | 'enum[' word (',' word)* ']'
           | '{' word ':' expr (',' word ':' expr)* '}' | "'" literal "'" | word

A word is a scalar (`SCALARS`) or a declared name. A map key is documentation (`map<slot, Text>`): keys are strings.
A `{source: path}` envelope is resolved by the reader before validation, so the compiler drops it from unions —
which also keeps msgspec from facing two untagged structs in one union."""

import keyword
import operator
import re
from dataclasses import dataclass
from functools import reduce
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal

import msgspec

from e_taxis.transpile.models.error import SchemaError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

##### DEFAULTS #####
TOKEN: Final = re.compile(r"\s*(?:(?P<sym>[<>\[\]{},:|])|'(?P<lit>[^']*)'|(?P<word>[A-Za-z0-9_./@$+*-]+))")
SCALARS: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "null": None,
        "any": Any,
        "path": str,
        "url": str,
        "date": str,
        "regex": str,
        "glob": str,
        "path-template": str,
        "core-path": str,
    }
)
ENVELOPE: str = "source"
STAR: str = "*"
END: tuple[str, str] = ("end", "")

type Leaf = tuple[str, ...]
type Token = tuple[str, str]


##### AST #####
@dataclass(frozen=True, slots=True)
class ScalarSchema:
    name: str


@dataclass(frozen=True, slots=True)
class LiteralSchema:
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ListSchema:
    item: Node


@dataclass(frozen=True, slots=True)
class MapSchema:
    value: Node


@dataclass(frozen=True, slots=True)
class RefSchema:
    name: str


@dataclass(frozen=True, slots=True)
class UnionSchema:
    options: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class FieldSchema:
    """`required`: no default. Otherwise `default`, or absent-as-None when it has none."""

    name: str
    node: Node
    required: bool = False
    default: Any = None


@dataclass(frozen=True, slots=True)
class StructSchema:
    name: str
    fields: tuple[FieldSchema, ...]

    @property
    def envelope(self) -> bool:
        return tuple(item.name for item in self.fields) == (ENVELOPE,)


type Node = ScalarSchema | LiteralSchema | ListSchema | MapSchema | RefSchema | UnionSchema | StructSchema


@dataclass(slots=True)
class CursorSchema:
    """The tokens of one type expression and how far the parser has read them."""

    text: str
    tokens: tuple[Token, ...] = ()
    at: int = 0

    def __post_init__(self) -> None:
        match re.fullmatch(rf"(?:{TOKEN.pattern})*\s*", self.text):
            case None:
                msg = f"type `{self.text}`: unreadable"
                raise SchemaError(msg)
            case _:
                self.tokens = tuple(
                    next((kind, value) for kind, value in token.groupdict().items() if value is not None)
                    for token in TOKEN.finditer(self.text)
                    if token.group().strip()
                )

    def peek(self) -> Token:
        return self.tokens[self.at] if self.at < len(self.tokens) else END

    def take(self, expected: str | None = None) -> str:
        kind, value = self.peek()
        match (kind, expected in (None, value)):
            case ("end", _) | (_, False):
                msg = f"type `{self.text}`: expected {expected or 'more'}, found {value or 'the end'}"
                raise SchemaError(msg)
            case _:
                self.at += 1
                return value


##### TYPES #####
class Schema:
    """One namespace of named types and the compiler over it. Pure: data in, types out; each struct built once."""

    __slots__ = ("_built", "_named", "_seq")

    def __init__(self) -> None:
        self._named: dict[str, Node] = {}
        self._built: dict[str, Any] = {}
        self._seq = 0

    ##### PRIVATE METHODS #####

    def _parse_expr(self, cursor: CursorSchema, owner: str) -> Node:
        first = self._parse_term(cursor, owner)
        match cursor.peek():
            case ("sym", "|"):
                cursor.take("|")
                rest = self._parse_expr(cursor, owner)
                return UnionSchema((first, *(rest.options if isinstance(rest, UnionSchema) else (rest,))))
            case _:
                return first

    def _parse_term(self, cursor: CursorSchema, owner: str) -> Node:
        match cursor.peek():
            case ("lit", value):
                cursor.take()
                return LiteralSchema((value,))
            case ("sym", "{"):
                cursor.take("{")
                self._seq += 1
                return StructSchema(name=f"{owner}{self._seq}", fields=self._parse_fields(cursor, owner))
            case ("word", "list"):
                cursor.take()
                cursor.take("<")
                item = self._parse_expr(cursor, owner)
                cursor.take(">")
                return ListSchema(item)
            case ("word", "map"):
                cursor.take()
                cursor.take("<")
                self._parse_expr(cursor, owner)
                cursor.take(",")
                value = self._parse_expr(cursor, owner)
                cursor.take(">")
                return MapSchema(value)
            case ("word", "enum"):
                cursor.take()
                cursor.take("[")
                return LiteralSchema(self._parse_words(cursor))
            case ("word", word):
                cursor.take()
                return ScalarSchema(word) if word in SCALARS else RefSchema(word)
            case (_, found):
                msg = f"type `{cursor.text}`: unexpected `{found or 'end'}`"
                raise SchemaError(msg)

    def _parse_fields(self, cursor: CursorSchema, owner: str) -> tuple[FieldSchema, ...]:
        """`name: expr` pairs up to the closing brace."""
        name = cursor.take()
        cursor.take(":")
        head = FieldSchema(name=name, node=self._parse_expr(cursor, f"{owner}_{name}"))
        match cursor.take():
            case ",":
                return (head, *self._parse_fields(cursor, owner))
            case "}":
                return (head,)
            case other:
                msg = f"type `{cursor.text}`: expected `,` or `}}`, found `{other}`"
                raise SchemaError(msg)

    def _parse_words(self, cursor: CursorSchema) -> tuple[str, ...]:
        """Enum values up to the closing bracket."""
        head = cursor.take()
        match cursor.take():
            case ",":
                return (head, *self._parse_words(cursor))
            case "]":
                return (head,)
            case other:
                msg = f"type `{cursor.text}`: expected `,` or `]`, found `{other}`"
                raise SchemaError(msg)

    def _common_resolve(self, node: Node) -> Node:
        match node:
            case RefSchema(name) if name in self._named:
                return self._common_resolve(self._named[name])
            case RefSchema(name):
                msg = f"type `{name}` is declared nowhere"
                raise SchemaError(msg)
            case _:
                return node

    def _common_envelope(self, node: Node) -> bool:
        match self._common_resolve(node):
            case StructSchema() as struct:
                return struct.envelope
            case _:
                return False

    @staticmethod
    def _compile_name(name: str) -> str:
        """An attribute msgspec can hold: `from` → `from_`, `argument-hint` → `argument_hint`."""
        clean = re.sub(r"\W", "_", name)
        return f"{clean}_" if keyword.iskeyword(clean) else clean

    def _compile_field(self, item: FieldSchema) -> tuple[Any, ...]:
        name, kind = self._compile_name(item.name), self.compile(item.node)
        match (item.required, item.default):
            case (True, _):
                return (name, kind)
            case (_, None):
                return (name, kind | None, None)
            case (_, default):
                return (name, kind, default)

    def _compile_struct(self, node: StructSchema) -> Any:
        match self._built.get(node.name):
            case None:
                ordered = sorted(node.fields, key=lambda item: not item.required)
                self._built[node.name] = msgspec.defstruct(
                    node.name,
                    [self._compile_field(item) for item in ordered],
                    kw_only=True,
                    frozen=True,
                    forbid_unknown_fields=True,
                    rename={self._compile_name(item.name): item.name for item in node.fields},
                )
                return self._built[node.name]
            case built:
                return built

    def _leaves_walk(self, node: Node, prefix: Leaf, seen: frozenset[str]) -> Iterator[Leaf]:
        match node:
            case RefSchema(name) if name in seen:
                yield prefix
            case RefSchema(name):
                yield from self._leaves_walk(self._common_resolve(node), prefix, seen | {name})
            case StructSchema() if node.envelope:
                yield prefix
            case StructSchema(_, fields):
                yield from (
                    leaf for item in fields for leaf in self._leaves_walk(item.node, (*prefix, item.name), seen)
                )
            case MapSchema(value):
                yield from self._leaves_walk(value, (*prefix, STAR), seen)
            case UnionSchema(options):
                nested = [
                    option
                    for option in options
                    if isinstance(self._common_resolve(option), StructSchema | MapSchema)
                    and not self._common_envelope(option)
                ]
                yield from (
                    (leaf for option in nested for leaf in self._leaves_walk(option, prefix, seen))
                    if nested
                    else (prefix,)
                )
            case _:
                yield prefix

    ### built at runtime from data: subscription spelled as the call it is, never a static type form.
    def _compile_scalar(self, node: ScalarSchema) -> Any:
        return SCALARS[node.name]

    def _compile_literal(self, node: LiteralSchema) -> Any:
        return Literal.__getitem__(node.values)

    def _compile_list(self, node: ListSchema) -> Any:
        return list.__class_getitem__(self.compile(node.item))

    def _compile_map(self, node: MapSchema) -> Any:
        return dict.__class_getitem__((str, self.compile(node.value)))

    def _compile_ref(self, node: RefSchema) -> Any:
        return self.compile(self._common_resolve(node))

    def _compile_union(self, node: UnionSchema) -> Any:
        return reduce(
            operator.or_, [self.compile(option) for option in node.options if not self._common_envelope(option)]
        )

    COMPILERS: ClassVar[Mapping[type, Callable[..., Any]]] = MappingProxyType(
        {
            ScalarSchema: _compile_scalar,
            LiteralSchema: _compile_literal,
            ListSchema: _compile_list,
            MapSchema: _compile_map,
            RefSchema: _compile_ref,
            UnionSchema: _compile_union,
            StructSchema: _compile_struct,
        }
    )

    ############################################################

    ##### PUBLIC #####

    def parse(self, text: str, owner: str = "T") -> Node:
        """One type expression into its AST."""
        cursor = CursorSchema(str(text))
        node = self._parse_expr(cursor, owner)
        match cursor.peek():
            case ("end", _):
                return node
            case (_, extra):
                msg = f"type `{text}`: trailing `{extra}`"
                raise SchemaError(msg)

    def declare(self, name: str, node: Node) -> Node:
        """A named type others may reference; returns it."""
        self._named[name] = node
        return node

    def field(self, owner: str, name: str, spec: Any) -> FieldSchema:
        """One field: a bare type string (optional), or `{type, required, default}`; `type: enum` takes `values`."""
        match spec:
            case str() as text:
                return FieldSchema(name=name, node=self.parse(text, f"{owner}_{name}"))
            case {"type": "enum", "values": list() as values}:
                node: Node = LiteralSchema(tuple(str(value) for value in values))
            case {"type": str() as text}:
                node = self.parse(text, f"{owner}_{name}")
            case _:
                msg = f"{owner}.{name}: a field is a type string or a mapping with `type`"
                raise SchemaError(msg)
        return FieldSchema(name=name, node=node, required=bool(spec.get("required")), default=spec.get("default"))

    def struct(self, name: str, fields: Mapping[str, Any]) -> StructSchema:
        """A struct from a field table."""
        return StructSchema(name=name, fields=tuple(self.field(name, key, spec) for key, spec in fields.items()))

    def compile(self, node: Node) -> Any:
        """The msgspec type of an AST node, dispatched on its variant. Envelopes vanish from unions."""
        return self.COMPILERS[type(node)](self, node)

    def validate(self, node: Node, value: Any) -> Any:
        """`value` converted to the compiled type; the message names the path that failed."""
        try:
            return msgspec.convert(value, self.compile(node))
        except msgspec.ValidationError as exc:
            raise SchemaError(str(exc)) from exc

    def leaves(self, node: Node) -> frozenset[Leaf]:
        """Every leaf path under `node`: a struct field descends, a map key is `*`, a list or a scalar ends a path."""
        return frozenset(self._leaves_walk(node, (), frozenset()))
