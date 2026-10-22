# msgspec — the boundary default

A C extension: `Struct` types with validation on decode and (de)serialization for JSON, MessagePack, YAML and TOML. The fastest option and the lowest memory — the default whenever data crosses a trust boundary under concurrency or stress and pure Python won't do.

```python
import msgspec

class Ingest(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    id: str
    weight: float = 0.0

data = msgspec.json.decode(raw, type=Ingest)   # validated on decode, no second pass
raw  = msgspec.json.encode(data)                # fast, allocation-light
```

- `Struct` options: `frozen`, `kw_only`, `omit_defaults`, `forbid_unknown_fields`, `tag`/`tag_field` for tagged unions (sum types → `arch-py-adt`), `gc=False` to skip GC on hot, cycle-free data.
- Validation is structural and strict on `decode`, and **only** there: a `Struct(...)` built in code skips every constraint. There is no validator DSL — a complex value or a model that must hold however it is born is a *checked model* (below); a whole domain of interlocking validators escalates to pydantic.
- `msgspec.Meta` via `Annotated` for constraints (`ge`, `le`, `pattern`, `min_length`).
- `msgspec.convert` moves between Structs, dataclasses and dicts with no serialization round-trip.
- `Struct` evaluates its annotations at class creation. A self-reference (`children: tuple[Box, ...]`) raises `NameError` there unless the module has `from __future__ import annotations` — put the import in the module; never keep the quote and silence ruff's UP037, which strips it under py3.14 deferred annotations.
- Loading a config **file** (json/jsonc/yaml/toml/ini, format by suffix) into a `Struct` → `e-serde` (`lang-py-stdlib`): it wraps msgspec and fills your `type=` model. `msgspec.json.decode` is for bytes you already hold in one known format.

## Checked models — complex types, validated however they are born

The modus operandi when a field is more than a builtin (a JSON Schema, a slug, weights that sum to one), or when the model may be built in code, not only decoded. One validation path, msgspec's own; nothing written twice.

1. **A complex type is a checked type**: a subclass of a builtin (`dict`, `list`, `tuple`, `str`, `int`, `float`) that validates in its constructor and raises `ValueError` — any third-party library allowed, derived state (a compiled validator) cached on itself in `__slots__`. Declare them first in the module; fields just name them.
2. **The model subclasses `CheckedStruct`** (frozen): decoded, msgspec validates it; built in code, `__post_init__` round-trips it through msgspec (`to_builtins` → `convert`) and the instance adopts the checked values — same errors, same locations (`- at $.output`).
3. **One hook pair**: `dec_hook` builds the checked type from its decoded form (so validates it); `enc_hook` returns the builtin it extends (msgspec encodes `dict`/`list`/`tuple` subclasses alone, never `str`/`int`/`float` ones). Anything else stays refused — a raw `dict` never slips into a `JsonSchema` field.
4. **Three places, never mixed**: one value's rule → its type; one field against another → `_check` (runs once per instance); one model against others → the collection's own rules.
5. **Decode trusted**: `CheckedStruct.convert(value, kind)` (or a decoder inside `CheckedStruct.trusted()` with `dec_hook=`) skips the round trip; forgetting it costs a redundant validation, never a missed one.
6. A generic model bounds its parameter to the loosest valid type (`class Spec[N: AnyName]`): built in code it holds to the bound, decoded as `Spec[Exact]` to the exact one.

```python
class JsonSchema(dict[str, Any]):                       # a checked type
    __slots__ = ("validator",)
    def __init__(self, value: Any = (), /) -> None:
        super().__init__(value)
        match self:
            case {"type": "object"} if jsonschema_rs.meta.is_valid(dict(self)):
                self.validator = jsonschema_rs.validator_for(dict(self))
            case _:
                raise ValueError("an object-rooted, valid JSON Schema")

class Spec(CheckedStruct, frozen=True, kw_only=True):
    name: Annotated[str, msgspec.Meta(pattern=NAME)]
    output: JsonSchema
    examples: tuple[dict[str, Any], ...] = ()

    def _check(self) -> None:                           # cross-field only
        match [i for i, ex in enumerate(self.examples) if not self.output.validator.is_valid(ex)]:
            case []: pass
            case bad: raise ValueError(f"examples {bad} do not match output")

spec = CheckedStruct.convert(raw, Spec)                # decoded: validated once
spec = Spec(name="x", output={"type": "array"})        # built: ValidationError ... - at `$.output`
```

`CheckedStruct` lives in the shared core (`core/struct.py`); ruff must list it in `runtime-evaluated-base-classes` beside `msgspec.Struct`, or it moves the annotation imports msgspec resolves at decode into `TYPE_CHECKING`.

Reach for it: light microservices, APIs, async workers, queues, realtime — the Litestar / Robyn stack. Not for deep validator logic or ORM binding: that is pydantic.
