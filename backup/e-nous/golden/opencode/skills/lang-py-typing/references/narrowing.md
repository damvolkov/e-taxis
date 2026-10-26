# narrowing — pinning, proving, reflecting

The tools that make the checker follow the value, prove a branch is impossible, and read types at runtime.

## Narrowing a union

The checker narrows automatically on `isinstance`, `is None`, `assert`, and `Literal` comparison. When the test is a custom predicate, tell it with a narrowing return:

```python
from typing import TypeIs

def is_nonempty(xs: list[T]) -> TypeIs[list[T]]:   # 3.13; narrows in BOTH branches
    return bool(xs)
```

- `TypeIs` (3.13) narrows on the true *and* false branch — the modern default.
- `TypeGuard` narrows only the true branch — use when the predicate is one-directional.

## Exhaustiveness

Prove every case of a union or enum is handled; a new variant then fails the check instead of slipping through:

```python
from typing import assert_never

match effect:
    case Increment(): ...
    case Remove(): ...
    case _ as unreachable: assert_never(unreachable)   # ty errors if a variant is unhandled
```

The `match` patterns themselves and the sum-type design are `arch-py-adt`; `assert_never` is the mechanic that makes the exhaustiveness a *checked* guarantee. It takes a value the checker has narrowed to **`Never`** — the bottom type no value inhabits; a function that never returns normally (it raises or exits) is typed **`NoReturn`**. Both let the checker prove a branch is dead.

## Pinning values and mutability

- `Literal["a", "b"]` — an exact set of values in a signature; narrows on comparison. `LiteralString` (PEP 675) — only literal-derived strings, so an API (SQL, shell) rejects attacker-tainted input at the type level.
- `Final` — a name that never rebinds; `@final` — a class or method that cannot be subclassed or overridden; `ClassVar[T]` — a class attribute never set from an instance (and, in pydantic-settings, never loaded from env).

## Reflection — only to generate

Reading types at runtime is for schema/codegen, not control flow:

- `get_origin(t)` / `get_args(t)` — decompose `list[int]` → `list`, `(int,)`; handle `UnionType`.
- `get_type_hints(obj, include_extras=True)` — resolve annotations, keeping `Annotated` metadata.
- Extract `Annotated` args to drive validation or serialization from the type alone.

## Escape hatches, ranked

`cast(T, x)` asserts a type the checker cannot prove — a last resort, and it is honest (visible, greppable). `# type: ignore` is **banned**: it hides the failure instead of asserting a fact. `TYPE_CHECKING` guards imports needed only for annotations (circular-import breaker) — the name exists to the checker, not at runtime, so quote the annotation or defer evaluation. Deferral: `from __future__ import annotations` (PEP 563) stringifies every annotation; **PEP 649** (default in 3.14) evaluates them lazily on demand, fixing forward refs and circular imports without the stringification footguns — prefer it, and resolve with `get_type_hints` when you must read a type at runtime.
