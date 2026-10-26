"""engine.model: the two schemas of an e-nous checkout, compiled — what the core may hold, what a spec may say.

`CoreModel` reads `core/schema.yaml`: the shared `types`, the persona registry, every entity and every config
module of each facet. Each facet compiles in its own namespace (`McpServer` differs between tekton and nomos).
`SpecModel` reads `specs/base.yaml`: its `types` and `kinds`, the root kind being `Spec`. Both are pure and built
once per read; validation raises SchemaError with the path msgspec names, and leaves feed the coverage law."""

from typing import TYPE_CHECKING, Any

from e_taxis.transpile.engine.schema import Leaf, Node, Schema
from e_taxis.transpile.models.error import SchemaError

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
ROOT: str = "Spec"
SHAPE: str = "shape"
FIELDS: str = "fields"
STRUCTS: str = "structs"
ASSETS: str = "assets"


##### TYPES #####
class CoreModel:
    """The core's shape per facet: persona, entities, config modules — compiled from `core/schema.yaml`."""

    __slots__ = ("_entities", "_modules", "_persona", "_raw", "_schemas")

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self._raw = raw
        self._schemas = {facet: self._init_schema() for facet in raw["facets"]}
        self._persona = {
            facet: schema.parse(raw["persona"][SHAPE], "Persona") for facet, schema in self._schemas.items()
        }
        self._entities = {name: self._init_entity(name, spec) for name, spec in raw.get("entities", {}).items()}
        self._modules = {
            facet: {
                name: self._init_module(facet, name, spec)
                for name, spec in raw["config"].get(facet, {}).items()
                if name != ASSETS
            }
            for facet in raw["facets"]
        }

    ##### PRIVATE METHODS #####

    def _init_schema(self) -> Schema:
        schema = Schema()
        _ = [schema.declare(name, schema.parse(spec[SHAPE], name)) for name, spec in self._raw.get("types", {}).items()]
        return schema

    def _init_structs(self, schema: Schema, structs: Mapping[str, Any]) -> None:
        _ = [schema.declare(name, schema.struct(name, fields)) for name, fields in structs.items()]

    def _init_entity(self, name: str, spec: Mapping[str, Any]) -> Node:
        schema = self._schemas[spec["facet"]]
        self._init_structs(schema, spec.get(STRUCTS, {}))
        return schema.struct(name.capitalize(), spec[FIELDS])

    def _init_module(self, facet: str, name: str, spec: Mapping[str, Any]) -> Node:
        schema = self._schemas[facet]
        self._init_structs(schema, spec.get(STRUCTS, {}))
        match spec:
            case {"shape": str() as shape}:
                return schema.parse(shape, name.capitalize())
            case {"fields": dict() as fields}:
                return schema.struct(name.capitalize(), fields)
            case _:
                msg = f"core/schema.yaml: config.{facet}.{name} declares neither `fields` nor `shape`"
                raise SchemaError(msg)

    ############################################################

    ##### PUBLIC #####

    @property
    def facets(self) -> Mapping[str, tuple[str, ...]]:
        """Facet → the layers it composes, in order."""
        return {facet: tuple(layers) for facet, layers in self._raw["facets"].items()}

    @property
    def entities(self) -> Mapping[str, str]:
        """Entity → the facet that holds its instances."""
        return {name: spec["facet"] for name, spec in self._raw.get("entities", {}).items()}

    def check_persona(self, facet: str, value: Any) -> Any:
        return self._schemas[facet].validate(self._persona[facet], value)

    def check_entity(self, name: str, value: Any) -> Any:
        return self._schemas[self.entities[name]].validate(self._entities[name], value)

    def check_module(self, facet: str, name: str, value: Any) -> Any:
        match self._modules[facet].get(name):
            case None:
                msg = f"config module `{name}` is not declared for facet {facet} in core/schema.yaml"
                raise SchemaError(msg)
            case node:
                return self._schemas[facet].validate(node, value)

    def entity_fields(self, name: str) -> frozenset[Leaf]:
        """The entity's top-level fields: what an instanced row's `from` names."""
        return frozenset((field,) for field in self._raw["entities"][name][FIELDS])

    def config_leaves(self, facet: str) -> frozenset[Leaf]:
        """Every leaf of every config module of the facet, module first: `mcp.servers.*.smoke`."""
        schema = self._schemas[facet]
        return frozenset(
            (module, *leaf) for module, node in self._modules[facet].items() for leaf in schema.leaves(node)
        )


class SpecModel:
    """What a backend spec may say — `specs/base.yaml` compiled, its root kind `Spec`."""

    __slots__ = ("_raw", "_root", "_schema")

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self._raw = raw
        self._schema = Schema()
        _ = [
            self._schema.declare(name, self._schema.parse(spec[SHAPE], name))
            for name, spec in raw.get("types", {}).items()
        ]
        _ = [
            self._schema.declare(
                name, self._schema.parse(spec[SHAPE], name) if SHAPE in spec else self._schema.struct(name, spec)
            )
            for name, spec in raw["kinds"].items()
        ]
        self._root = self._schema.parse(ROOT, ROOT)

    ##### PUBLIC #####

    @property
    def version(self) -> str:
        return str(self._raw["version"])

    @property
    def combinators(self) -> Mapping[str, Any]:
        return self._raw.get("combinators", {})

    @property
    def kinds(self) -> tuple[str, ...]:
        """The finding kinds the model's report declares."""
        return tuple(self._raw.get("report", {}).get("kinds", {}))

    def check(self, value: Any) -> Any:
        """A spec validated against the compiled `Spec`; SchemaError names the path."""
        return self._schema.validate(self._root, value)
