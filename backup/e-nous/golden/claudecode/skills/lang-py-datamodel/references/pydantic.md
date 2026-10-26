# pydantic v2 — the enterprise escalation

`BaseModel` on a Rust core (`pydantic-core`): rich validation, coercion, JSON Schema and the deepest ecosystem. Slower and heavier than msgspec, but unmatched for complex, interconnected models and configurability. Reach for it when concurrency is not the constraint.

```python
from pydantic import BaseModel, ConfigDict, field_validator, computed_field

class Account(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    balance: float

    @field_validator("balance")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0: raise ValueError("balance must be ≥ 0")
        return v

    @computed_field
    @property
    def overdrawn(self) -> bool: return self.balance == 0
```

- `model_config` (`ConfigDict`) is the reason to choose it: `extra`, `frozen`, aliases, `str_strip_whitespace`, arbitrary types — configure for almost any case.
- `field_validator`/`model_validator` for cross-field and business rules; `computed_field` for derived data; `TypeAdapter` to validate loose structures without a model.
- Database-bound modeling: **SQLModel** (pydantic + SQLAlchemy), SQLAlchemy 2, Tortoise ORM — the fine control pydantic gives over complex schemas.
- `pydantic-settings` for configuration → Engineering soul #16.

Reach for it: enterprise, monoliths, multi-maintainer apps, deterministic graph systems, ORM-heavy domains — the FastAPI stack. Otherwise msgspec.
