# Pure Python models

The floor and the default. Data you construct from typed code needs no validation library — it needs storage, immutability and identity, which the stdlib gives for free. Present in every system, even beside msgspec or pydantic.

## The choice

| Need | Reach for | Notes |
|---|---|---|
| A record you build and own | `@dataclass(slots=True, frozen=True)` | slots = less memory, no stray attributes; frozen = hashable, immutable |
| Mutable internal state | `@dataclass(slots=True)` | drop `frozen` only when the object must change |
| The shape of a dict you already have | `TypedDict` | static only — no runtime cost, no validation |
| A small named positional tuple | `NamedTuple` | immutable, iterable, unpackable |
| A closed set of constants | `StrEnum` / `IntEnum` + `auto()` | never bare string constants |

## dataclass — the workhorse

```python
from dataclasses import dataclass, field

@dataclass(slots=True, frozen=True, kw_only=True)
class Node:
    id: str
    weight: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)   # never a mutable default
```

- `slots=True` (3.10+): each subclass declares only its own; incompatible with a non-field class default, and with `cached_property` unless `__dict__` is re-added.
- `frozen=True`: immutable and hashable; assign through `object.__setattr__` inside `__post_init__` if you must.
- `kw_only=True` (3.10+): keyword-only fields, so field order and inheritance stop biting.
- `field(default_factory=...)` for any mutable default.

## TypedDict — shape without cost

```python
from typing import TypedDict, NotRequired, ReadOnly

class Row(TypedDict):
    id: ReadOnly[str]              # 3.13 (PEP 705) — the checker forbids mutation
    weight: float
    label: NotRequired[str]        # 3.11 — the key may be absent
```

Static shape for a dict moving through your own code. No validation, no serialization — the moment either is needed at a trust boundary, escalate to a validating boundary model.

## Modern surface (≥3.13)

- `Self` for fluent returns and `from_*` alternative constructors.
- PEP 695 generics: `class Box[T]:` and `type Alias = ...` — no `TypeVar` boilerplate.
- `enum.StrEnum`, `@enum.property`, `enum.member`/`nonmember`.
- Behaviour on these — comparison, emulation, descriptors — belong to the object model, not wrapper methods.
