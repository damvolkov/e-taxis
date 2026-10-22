# sentinels — typing absence without overloading None

When `None` is itself a **valid value**, it cannot also mean "not provided". A cache stores `None`; an optional update leaves a field untouched; a default must differ from every real argument. The answer is a **sentinel**: a unique singleton whose *type* the checker can track and narrow.

## The enum-of-one idiom (typed, the modern default)

A bare `_MISSING = object()` works at runtime but is untyped — the checker sees `object`, cannot narrow it, and cannot exhaust it. Give the sentinel a singleton type instead:

```python
from enum import Enum
from typing import Literal, Final

class _Sentinel(Enum):
    MISSING = object()

MISSING: Final = _Sentinel.MISSING
type Missing = Literal[_Sentinel.MISSING]   # a type with exactly one value

def get(key: str, default: T | Missing = MISSING) -> T | None:
    hit = _store.get(key, MISSING)
    if hit is MISSING:                       # narrows: below here hit is T, not Missing
        ...
    return hit
```

`Literal[_Sentinel.MISSING]` is a type inhabited by that one object, so `is MISSING` narrows the union in both branches and `assert_never` can prove exhaustiveness over `T | Missing`.

## Why not the alternatives

- `None` for "unset" **when `None` is a legal value** — the classic bug: the two meanings collapse and you cannot tell "stored `None`" from "absent".
- `object()` sentinel — untyped, no narrowing, no exhaustiveness.
- A dedicated class with a single instance also works (`class _Missing: ...; MISSING: Final = _Missing()`), typed by the class itself; the enum idiom is terser and gives a clean `repr`.
- PEP 661 (a stdlib `sentinel`) is not accepted as of 2026 — the enum idiom is the portable answer.

## Where each concern lives

Optional/unset **fields of a domain model** (partial updates, "not set" vs "null") are typed by the model kind — pydantic's `Unset`, msgspec's `UNSET` → `lang-py-datamodel`. This file is the language-level pattern for a sentinel value in ordinary function and cache APIs. "Never returns" is not absence — that is `NoReturn`/`Never`, a narrowing concern.
