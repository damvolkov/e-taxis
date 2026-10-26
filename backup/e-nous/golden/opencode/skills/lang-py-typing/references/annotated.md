# annotated — metadata without changing the type

`Annotated[T, m1, m2, …]` is a channel: **`T` is the type** the checker sees, the rest is metadata that tools read at runtime. The base type is unchanged — code that ignores the metadata still type-checks against `T`.

```python
type TagField = Annotated[str, "tag"]      # still a str to ty; "tag" is a marker for schema-gen
type Port = Annotated[int, Gt(0), Lt(65536)]
```

## Compose and extract

- Multiple metadata items stack, order preserved, on `__metadata__`; nesting flattens (`Annotated[Annotated[int, a], b]` == `Annotated[int, a, b]`).
- Read them with `get_type_hints(obj, include_extras=True)` (drop `include_extras` and the metadata is stripped — the whole point of the channel is it is opt-in).
- Pull specific markers with `get_args(hint)` then filter by `isinstance`; that is how validators, DI and serializers are driven from the type alone.

```python
hints = get_type_hints(fn, include_extras=True)
metas = [m for m in get_args(hints["port"])[1:] if isinstance(m, Constraint)]
```

## What the markers are for

- **Semantic tags** — a role a schema generator or serializer keys on (`"tag"`, a field kind).
- **Constraints / units** — a value's rule or unit; the *validation engine* that enforces them is a data-model concern → `lang-py-datamodel`, `arch-py-adt`. Here: attach and extract, not the engine.
- **DI markers** — `Annotated[Service, Depends(...)]`: the type resolves the dependency, the marker says how. The framework-native form → the API skill's `lib.md`.
- **Documentation** — `Annotated[int, Doc("retry budget")]` (PEP 727) carries prose the checker ignores and tools surface.

## Rule

The metadata is additive, never load-bearing for the type: a reader that drops `include_extras` must still get a correct, usable `T`. If the annotation only makes sense *with* its metadata, it is a `NewType` or a validated alias (`arch-py-adt`), not a bare `Annotated`.
