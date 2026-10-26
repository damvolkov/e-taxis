---
name: lang-py-typing
description: "Python: advanced strong typing — PEP 695 generics, ParamSpec, overloads, Protocols, narrowing, exhaustiveness, sentinels. Use when a plain annotation is not enough. Not layout, naming or cost."
metadata:
  family: form
---

# lang-py-typing

Make the type the strongest contract the code can carry: everything annotated, no escape hatch, checked twice — statically and at runtime. Owns the language-level typing toolbox and the two gates. Not here: the patterns that *consume* types — newtype/parse-don't-validate/sum types (`arch-py-adt`), `__slots__`/descriptors/model kinds (`lang-py-datamodel`), typed dispatch (`para-py-dispatch`), iterator protocols (`para-py-iteration`), their naming (`tax-py-naming`). The checker/enforcer stack → `references/lib.md`.

## Rules

1. **Everything typed; no escape hatch.** No bare `Any` except at an untyped third-party edge; **never `# type: ignore`** — fix the annotation. Modern syntax only: `X | None`, `list[int]`, `Self` — never `Optional`/`List`/`Union`.
2. **Generics are PEP 695.** `class Store[T: Node]:`, `def first[T](xs: list[T]) -> T`, `type Alias[T] = ...`; bound every parameter, give a default where one fits (`[T = str]`, PEP 696), let variance infer, and let aliases recurse for nested data. → `references/generics.md`
3. **Decorators and returns keep their shape.** `ParamSpec` (`[**P, T]`, `Concatenate` when injecting) preserves a wrapped signature; `@overload` types input-driven returns; `Self` types fluent and `classmethod` returns; `@override` (3.12) pins intent. → `references/generics.md`
4. **Structural over nominal.** A `Protocol` is the interface contract — over an ABC; `@runtime_checkable` only when you must `isinstance` it. (Protocol *for dispatch* → `para-py-dispatch`.) → `references/structural.md`
5. **Narrow, exhaust, pin.** `TypeGuard`/`TypeIs` narrow, `assert_never` proves exhaustiveness, `Never`/`NoReturn` mark the bottom, `Literal`/`Final`/`ClassVar`/`LiteralString` pin values, mutability and injection-safety. → `references/narrowing.md`
6. **`Annotated` carries metadata; sentinels type absence.** `Annotated[T, meta]` attaches a validator, marker or unit without changing `T` (read via `get_type_hints(…, include_extras=True)`); a sentinel is a distinct singleton so *unset* is its own type, never an overloaded `None`. → `references/annotated.md` · `references/sentinels.md`
7. **Checked twice, reflected sparingly.** `ty` (Astral, Rust) static in CI, `beartype` runtime on business-logic classes (O(1), stays on in prod); reflect (`get_args`/`get_type_hints`) only to generate; `TYPE_CHECKING` and deferred annotations (PEP 649, 3.14) keep imports and forward refs cheap. → `references/lib.md`

## Sample

```python
from collections.abc import Callable, Awaitable
from functools import wraps
from beartype import beartype

def timed[**P, T](fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """The wrapped signature survives exactly — args and return type are preserved."""
    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:   # ParamSpec: no signature loss
        return await fn(*args, **kwargs)
    return wrapper

@beartype                                   # runtime contract; ty checks the same statically
class Store[T: Node]:                        # PEP 695 generic, bound to Node
    def put(self, key: str, value: T) -> Self: ...
```

`[**P, T]` keeps the decorator transparent to the checker; `[T: Node]` bounds the container; `@beartype` enforces both at runtime. No `Any`, no `# type: ignore`.

## References

- `references/generics.md` — PEP 695 generics, TypeVar/ParamSpec/TypeVarTuple, defaults (PEP 696), variance, recursive aliases, overloads, Self/override
- `references/structural.md` — Protocol as contract, runtime_checkable, structural vs nominal, the ABC boundary
- `references/annotated.md` — `Annotated` done right: metadata channel, extraction, composition, semantic markers, `Doc`
- `references/sentinels.md` — sentinels and typing absence: missing/unset singletons, `Never`/`NoReturn`, the `None`-overload trap
- `references/narrowing.md` — TypeGuard/TypeIs, assert_never, Literal/Final/ClassVar/LiteralString, cast, reflection, TYPE_CHECKING, deferred annotations
- `references/lib.md` — the stack: static checker (`ty`) and runtime enforcer (`beartype`), and what each replaces
