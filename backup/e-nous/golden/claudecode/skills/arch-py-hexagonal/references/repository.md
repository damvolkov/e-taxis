# Repository

A repository is a driven port that makes storage look like an in-memory collection of domain objects. The core says `store.get(id)` and `store.add(entity)`; it never knows there is Redis, Postgres or a vector index behind it. Rust anchor: a `trait Store` the domain owns, `impl`'d per backend.

## The shape

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class KnowledgeStore(Protocol):                          # port in the core
    async def get(self, id: str) -> Entity | None: ...
    async def add(self, entity: Entity) -> None: ...
    async def search(self, query: QueryEntity) -> list[MatchedEntity]: ...
```

- The port speaks in **domain types** (`Entity`, `QueryEntity`), never in rows, documents or vendor DTOs.
- One repository per aggregate, not per table. `KnowledgeStore` owns `Entity` and its parts; a second aggregate gets its own store.
- Methods are named from the domain vocabulary (`get`/`add`/`search`), not the backend (`hget`/`upsert`/`knn`). → `tax-py-naming`

## Why, not just how

- **Substitutable persistence.** FakeStore in tests, RedisStore in prod, PostgresStore next quarter — the core is untouched. This is the payoff of DIP made concrete.
- **The domain stays pure.** No `redis` import crosses into the core; the query language of the backend never leaks upward.
- **Testability.** A dict-backed fake implementing the Protocol turns integration tests into unit tests.

## Query objects over method explosion

When queries grow parameters, do not breed `search_by_tag_and_score_and_date`. Pass a **query object** — a frozen dataclass the core builds and the adapter interprets.

```python
@dataclass(frozen=True, slots=True)
class QueryEntity:
    text: str
    tags: frozenset[str] = frozenset()
    min_score: float = 0.0
    limit: int = 10
```

The adapter translates the query object into the backend's dialect (a `HybridQuery`, a SQL `WHERE`, a filter dict) at the edge. New criteria = a new field, not a new method. This keeps the port small (ISP).

## Unit of Work — the transactional boundary

When several repository writes must commit or roll back together, wrap them in a Unit of Work: an async context manager that opens a transaction, exposes the repositories, and commits on clean exit / rolls back on exception.

```python
async with uow:                       # begins a transaction
    await uow.entities.add(entity)
    await uow.threads.add(thread)
    await uow.commit()                # atomic; __aexit__ rolls back if commit never ran
```

RAII again: the scope owns the transaction. → `lang-py-lifecycle`. Reach for a UoW only when you have **multiple writes that must be atomic** — a single write does not need one.

## When NOT to

- A cache with no domain identity (a raw `redis.get(key)` for a rate-limit counter) is infrastructure, not an aggregate — do not dress it as a repository.
- Read-heavy analytics that must exploit the backend's engine (a Polars scan, a bespoke SQL). Forcing it through a generic port throws away the performance you chose that backend for — expose a purpose-built read port instead, or drop to the backend deliberately and say why.

Concrete storage clients (Redis, vector indexes, dataframes) are the province of → `data-py-*`; this skill governs only the *shape of the boundary*.
