---
name: lang-py-datamodel
description: "Python: pick and shape the data model — pure dataclasses/TypedDict, msgspec or pydantic by software category; slots, frozen, descriptors, dunders. Use when defining a model, DTO or value object."
metadata:
  family: form
---

# lang-py-datamodel

Model data with the lightest tool that holds the invariant. Pure Python is the floor and lives in every system; msgspec is the boundary default under load; pydantic is the escalation for complex or enterprise domains. Only these three. And within any of them, bake behaviour into the object — never a getter that reimplements a dunder.

## Rules

1. **Pure Python is the floor.** Interior, code-controlled data → `@dataclass(slots=True, frozen=True)`; a dict shape for the checker → `TypedDict`; `StrEnum`/`NamedTuple` where they fit. Present even beside msgspec or pydantic. → `references/pure.md`
2. **msgspec at the boundary under load.** Data crossing a trust boundary (network, user, LLM, queue) in an API, worker or any high-concurrency, stress-bearing service → `msgspec.Struct`. The default the moment pure Python won't do. → `references/msgspec.md`
3. **pydantic for complex or enterprise.** Deeply interconnected models, monoliths, multi-maintainer apps, ORM-bound (SQLModel/SQLAlchemy/Tortoise) or heavy `model_config` — where concurrency is not the constraint. → `references/pydantic.md`
4. **One boundary model, pure interior.** msgspec *or* pydantic at the edge, never both; value objects, graph nodes and loggers inside stay pure Python. The choice traces to the software category → `references/lib.md`.
5. **Bend the object model.** `__slots__`, descriptors, properties and identity dunders bake behaviour in; delete any getter, `is_x()` or `to_str()` that reimplements a dunder. → `references/mechanics.md`
6. **Value semantics by construction.** `frozen=True` for hashable immutables; `__repr__`/`__eq__`/`__hash__`/ordering come from the dataclass or `functools.total_ordering`, never hand-written. → `references/mechanics.md`
7. **Validate once, at the edge — and wherever a model is born.** The boundary model coerces on decode; the interior trusts its types. A msgspec model with complex types, or built in code, is a checked model: checked types + `CheckedStruct`, one path. → `references/msgspec.md` · runtime typing → `lang-py-typing`; failure paths → `lang-py-lifecycle`.

## Sample

```python
from dataclasses import dataclass
from typing import TypedDict
import msgspec

@dataclass(slots=True, frozen=True)          # interior, code-owned → pure Python
class Node:
    id: str
    weight: float

class Row(TypedDict):                         # a dict shape for the checker only
    id: str
    weight: float

class Ingest(msgspec.Struct, frozen=True):    # crossing the wire under load → validated, fast
    id: str
    weight: float
```

Three tiers, one system: `Ingest` guards the boundary, `Node` is the trusted interior, `Row` is a shape the type checker sees. pydantic would replace `Ingest` only in a complex or enterprise domain.

## References

- `references/pure.md` — pure-Python models: `dataclass` (slots/frozen/kw_only), `TypedDict`, `NamedTuple`, `StrEnum`, modern ≥3.13
- `references/mechanics.md` — bend the object model: slots, descriptors, properties, identity/emulation/construction/serialization dunders
- `references/msgspec.md` — the boundary default: `Struct`, encode/decode, validation, speed; checked models (complex types, built in code)
- `references/pydantic.md` — the enterprise escalation: `BaseModel`, `model_config`, validators, ORM
- `references/lib.md` — the three-model stack mapped to software category
