# generics — parametric typing (PEP 695)

Python 3.12+ makes generics first-class syntax. Use it; the old `TypeVar("T")` + `Generic[T]` ceremony is legacy.

## Declaration

```python
class Store[T: Node]:                 # T bound to Node; T | subclasses only
    def get(self, key: str) -> T | None: ...

def first[T](xs: list[T]) -> T: ...   # inferred from the argument
type Pair[T] = tuple[T, T]            # parametrized alias
```

- **Bound** — `[T: Node]`: T is Node or a subclass. Almost always bound; an unbounded `[T]` is rarely what you mean.
- **Constrained** — `[T: (int, str)]`: T is exactly one of the listed types, not a common base.
- **Default** — `[T = str]` (PEP 696, 3.13): a type argument that may be omitted, so `Store` means `Store[str]`. A defaulted parameter follows the non-defaulted ones, exactly like function defaults.
- Each subclass **re-declares** its parameters: `class KVStore[T: Node](Store[T]):` — generics do not inherit implicitly.

## Recursive types

A type that refers to itself — nested JSON, trees, expression ASTs. A PEP 695 `type` alias may recurse directly; the checker resolves the forward reference lazily:

```python
type JSON = None | bool | int | float | str | list[JSON] | dict[str, JSON]

class Tree[T]:                          # recursive generic structure
    value: T
    children: list[Tree[T]]             # forward ref to the enclosing class
```

Recursion in the *type* is free; recursion in the *code* that walks it is bounded by the frame ceiling — traverse deep structures iteratively (an explicit stack), not recursively → `para-py-iteration`. Type the walker's return as the recursive alias so exhaustiveness holds at every level.

## Variance

The checker infers variance in 3.12+; you rarely annotate it. The intuition:
- **Covariant** — a producer/read-only container (`Sequence[Cat]` is a `Sequence[Animal]`).
- **Contravariant** — a consumer (`Callable[[Animal], None]` is a `Callable[[Cat], None]`).
- **Invariant** — a mutable container (`list[Cat]` is *not* `list[Animal]`). Default for anything writable.

## ParamSpec — signature-preserving decorators

```python
def guard[**P, T](fn: Callable[P, T]) -> Callable[P, T]: ...   # args + return survive
```

- `P.args`/`P.kwargs` in the wrapper thread the original parameters through untouched.
- `Concatenate[Request, P]` when the decorator **injects** a leading argument.
- Without `ParamSpec`, a decorator erases the signature to `(*args, **kwargs)` — a silent loss of type safety.

## TypeVarTuple — variadic generics

`def broadcast[*Ts](x: tuple[*Ts]) -> tuple[*Ts]: ...` for shape-preserving array/tensor code where the number of type parameters varies. Niche; reach for it only when the arity is genuinely variable.

## Overloads and Self

- `@overload` — different return types by input type; write the overload signatures, then one untyped implementation. For value/type *dispatch* the mechanism is `para-py-dispatch`; here `@overload` is for return-type polymorphism the checker must see.
- `Self` — the return type of fluent methods and `classmethod` constructors: `def with_tag(self, t: str) -> Self` returns the subclass, not the base.
- `@override` (3.12) — declares a method overrides a base; the checker flags a rename that silently breaks the link.
