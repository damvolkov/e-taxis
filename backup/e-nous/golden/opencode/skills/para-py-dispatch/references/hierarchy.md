# Picking the level

| What varies | Level | Why |
|---|---|---|
| Argument types | Multiple dispatch | The signature is the condition; several arguments, coroutines, generics |
| A value from a closed set | Frozen mapping | O(1), a new case is a new row, trivially testable |
| A value from an open set | Registry | Handlers declare themselves; the dispatcher never changes |
| Nested structure, mixed types | `match-case` | Destructure, type-test and bind in one pattern |
| Two outcomes, one expression | Ternary | The only surviving conditional |

## 1. Typed multiple dispatch

`ovld` first: several arguments, `Literal` types, coroutines. `plum-dispatch` when `ovld` cannot express the signature. `functools.singledispatch` only when no dependency is allowed — first argument only, no async.

A custom dispatcher is justified when resolution depends on something the libraries cannot see: a runtime capability, a protocol version, a feature flag. It stays one lookup, never a chain.

The **Visitor** pattern is this written by hand — `accept`/`visit` double dispatch to fake type-based selection in a language that lacked it. Python has it: an `@ovld` overload set replaces the whole scaffolding, and a closed variant set is better matched exhaustively (→ arch-py-adt). The classic pattern is the anti-pattern here.

## 2. Frozen mapping

```python
HANDLERS: Final[Mapping[Kind, Handler]] = MappingProxyType({...})
```

`Final` states the intent to the type checker; `MappingProxyType` enforces it at runtime. Use both when the table is importable by other modules.

A missing key is an error, not a default. `HANDLERS[kind]` raising `KeyError` is correct; `.get(kind, fallback)` only when the fallback is genuine domain behaviour.

## 3. match-case, at both extremes

Trivial end — three literal cases and no structure; a table would be more machinery than the problem deserves.

Complex end — the condition *is* the shape:

```python
match event:
    case Order(total=total, items=[_, *_]) if total > LIMIT:
        return Escalate(total)
    case Order(items=[]):
        return Reject(Reason.EMPTY)
```

Guards belong in the pattern, never in the body. A `match` whose cases are all bare literals is a mapping in disguise — convert it.

## Permitted conditionals

| Form | Allowed |
|---|---|
| `x if cond else y` inside a comprehension or assignment | Yes |
| Walrus guard returning early on a sentinel | Yes, one per function |
| `if not x: raise` at a boundary | Yes — validation, not branching |
| Two or more branches selecting behaviour | No. Use the hierarchy |
| `elif` | Never |

## Cost

Mapping lookup is O(1) and constant in edits. A conditional chain is O(n) in branches and O(n) in edits as the domain grows. Multiple dispatch resolves once and caches. → `algo-gen-selector`
