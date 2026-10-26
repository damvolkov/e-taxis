---
name: para-py-dispatch
description: "Python: conditionals are banned; select behaviour with typed multiple dispatch, a frozen mapping or match-case. Use when writing or reviewing any branching, handler selection or type-based behaviour."
metadata:
  family: form
---

# para-py-dispatch

`if/elif` is a decision table nobody wrote down. Write the table.

## Rules

1. **The hierarchy.** Take the first that fits:
   1. **Typed multiple dispatch** — `ovld`, `plum-dispatch`, or a custom dispatcher. Async-friendly, the signature *is* the condition. Default choice.
   2. **Frozen mapping** — `Final[Mapping[Enum, Handler]]`, O(1) retrieval, open to new rows.
   3. **`match-case`** — at both extremes only: a case trivial enough that a table is ceremony, or one complex enough that types and structure must be destructured in the pattern itself.
2. **`if/else` is banned.** It survives only as a ternary inside a comprehension or a single binary expression assignment. Two `if`s in a row means the mechanism is wrong.
3. **No loops.** No `for`, no `while`. Comprehensions and functional operators. → `para-py-iteration`
4. **Methods live in their class.** Dispatch is the only exception: handlers and overloads may be module-level atomic functions, because the dispatcher must reach them without an instance.
5. **Keys are `StrEnum` members.** A raw string key is an unvalidated branch. The mapping is `Final` and immutable — `MappingProxyType` when it escapes the module.
6. **No `isinstance` chains.** That is hand-written multiple dispatch. Use `ovld` or class patterns in `match-case`.
7. **Walrus binds and tests once**, in positive and negative guards alike.

## Sample

```python
class Kind(StrEnum):
    VECTOR = auto()
    HYBRID = auto()

# Type decides → multiple dispatch. Handlers are module-level by necessity.
@ovld
async def render(node: TextNode) -> str: ...
@ovld
async def render(node: ImageNode) -> str: ...

# Value decides → frozen mapping. A new kind is a new row, never a new branch.
BUILDERS: Final[Mapping[Kind, Callable[[Spec], Query]]] = MappingProxyType({
    Kind.VECTOR: VectorQuery.from_spec,
    Kind.HYBRID: HybridQuery.from_spec,
})
query = BUILDERS[kind](spec)   # a missing key raises — correct, not a default
# Structure decides → match-case, destructuring and typing in the pattern.
def read_effect(payload: Mapping[str, object]) -> Effect:
    """Effect parsed from an untyped payload."""
    match payload:
        case {"op": "add", "value": int() | float() as value}:
            return Increment(value)
        case {"op": "del", "key": str() as key}:
            return Remove(key)
        case _:
            raise UnknownEffectError(payload)
```

## References

- `references/hierarchy.md` — picking the level, and the permitted `if` exceptions
- `references/registry.md` — self-registering handlers, no table to edit
- `references/lib.md` — the dispatch stack: builtin mapping → `ovld`/`plum-dispatch`, async·sync, by software category
