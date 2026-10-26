# Result — errors as values

An expected failure is data the caller must handle, so make it part of the return type. `Result[T, E]` is a sum type with two variants — `Ok(value)` or `Err(error)` — and the caller `match`es both. Rust anchor: `Result<T, E>` and the `?` operator; the failure travels in the type, not through a side channel.

## The type

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Ok[T]: value: T
@dataclass(frozen=True, slots=True)
class Err[E]: error: E
type Result[T, E] = Ok[T] | Err[E]
```

This is the project baseline (also in the N5 rule). For most code it is all you need — no dependency.

## Result vs exception — the boundary

The dividing line is **who is meant to react**.

| Situation | Mechanism | Why |
|---|---|---|
| The caller can sensibly handle it | `Result` | "not found", "invalid input", "rate-limited" — a normal outcome, part of the contract |
| Nothing local can recover | exception | out of memory, programmer bug, a broken invariant — crash toward a handler |
| A boundary crossing (HTTP, DB) | catch → convert | the adapter turns the vendor exception into a domain `Err` at the edge |

Exceptions are **not control flow**. `try/except` used to choose between two normal paths is a sum type written badly. Raise at the exceptional, catch once at the boundary, convert to `Result` inward. → `lang-py-lifecycle` for the exception discipline.

## Error as a sum type, not a string

`E` should itself be a closed set, so the caller's `match` is exhaustive and every failure mode is named.

```python
type FetchError = Literal["not_found", "unauthorized", "timeout"]

async def fetch_user(uid: str) -> Result[User, FetchError]:
    match await self._store.get(uid):
        case None:  return Err("not_found")
        case user:  return Ok(user)

match await fetch_user(uid):
    case Ok(user):          render(user)
    case Err("not_found"):  return http_404()
    case Err("timeout"):    return http_503()
    case Err("unauthorized"): return http_401()
```

## Railway-oriented composition

Chained steps that each may fail should short-circuit on the first `Err` without a pyramid of `if`. Compose the happy path; the failure path flows around it — Rust's `?`.

```python
def bind[T, U, E](r: Result[T, E], f: Callable[[T], Result[U, E]]) -> Result[U, E]:
    match r:
        case Ok(v):  return f(v)
        case Err():  return r          # short-circuit; the error rides through untouched

result = bind(bind(parse(raw), validate), persist)   # stops at the first Err
```

For deep chains, async railways, or monadic style (`Maybe`, `IO`, `.map`/`.bind`, `@safe`), reach for a library instead of hand-rolling combinators → `lib.md`.

## Option — absence as a value

Absence is the degenerate `Result` with no error payload. Python already has it: `T | None` + the walrus, matched or guarded once.

```python
if (user := cache.get(uid)) is not None:
    return user
```

Do not build an `Option` class where `T | None` reads cleanly — that is ceremony the language already handles. Reach for a real `Maybe` only when you want to chain many nullable steps without nested walruses → `lib.md`.

## When NOT to

- A function that cannot fail returns its value plainly — wrapping everything in `Ok` is noise.
- Deep inside a pure core where any failure is a bug: raise; there is no sensible local handling, and a `Result` no one inspects is worse than a crash.
