# lib — the data-model stack

Three models, and nothing else. Pure Python is the floor and is always present; msgspec is the boundary default under load; pydantic is the escalation for complex or enterprise systems. Native over pure Python holds: msgspec is a C extension, `pydantic-core` is Rust.

## By software category

| Category | Model | Why |
|---|---|---|
| System script · simple automation · serverless | **pure Python** | no trust boundary, no validation to pay for |
| Library | **pure Python** | forces no dependency on the consumer |
| Interior of any system — value objects, graph nodes, loggers | **pure Python** | always present, types already trusted |
| API service (light) · Async worker · queues · high-concurrency | **msgspec** | boundary validation + serialization at top speed |
| Voice runtime · realtime under stress | **msgspec** | lowest latency and memory |
| API service (enterprise, monolith, multi-maintainer) | **pydantic** | deep validation, `model_config`, ecosystem |
| ML pipeline · Agent system — complex, interconnected, speed secondary | **pydantic** | fine control over intricate models |
| Database-bound — SQLModel / SQLAlchemy / Tortoise | **pydantic** | ORM integration and schema control |
| Agent system · ML pipeline — a schema received as data (MCP `inputSchema`, tool-call arguments, foreign contracts) | **jsonschema-rs** | validates against the schema itself; no model mirrors it |

## The rule

Whenever pure Python won't do, **msgspec by default** — unless the models are very complex and interconnected and concurrency is not the constraint, then **pydantic**. The framework choice mirrors it: **Litestar / Robyn + msgspec**, **FastAPI + pydantic**.

When the schema is **data, not a class** — a JSON Schema you receive rather than write — compile it once with **`jsonschema-rs`** (`validator_for`, then `is_valid` / `iter_errors` / `validate`) and validate against it; `$ref` across documents goes through its `Registry`. A schema you own still starts as a model and is exported from it (`msgspec.json.schema`, `model_json_schema`).

## Stack

| Model | Backend | Use |
|---|---|---|
| `dataclasses` · `TypedDict` · `NamedTuple` · `enum` | stdlib | interior, code-controlled data |
| `msgspec` | C | boundary under load |
| `pydantic` v2 (`pydantic-core`) | Rust | complex / enterprise / ORM |
| `jsonschema-rs` | Rust | JSON Schema as data, Draft 4 → 2020-12 — MIT, v0.58.6 (2026-10-06) |

**Never:** a validation library for interior data you already typed · two boundary models in one system · pydantic where msgspec carries the load · a bare dict where a `TypedDict` or `Struct` states the shape · a hand-written model mirroring a schema you received · a schema compiled per call.
