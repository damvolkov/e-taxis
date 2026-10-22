# lib — the event stack

What to reach for to *build* event-driven services — the framework, the in-process bus, the event store, the schema. The **transport** (which broker: NATS/Redpanda/Kafka) is `sys-gen-scaling`, not this list; the **async handler** machinery is `conc-py-async`; the **event/command types** are `lang-py-datamodel`. Reach order: builtin (`asyncio.Queue`, frozen dataclasses) → `faststream` (service framework) → `eventsourcing`/KurrentDB (sourcing). Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The event stack × the nine software categories.

| Category | Event stack |
|---|---|
| **API service** | emit domain events via the outbox; `faststream` sidecar consumer |
| **Async worker** | `faststream` consumers over the broker — the core use; autoscale on lag → `sys-gen-scaling` |
| **ML pipeline** | events as sample/stage stream; `faststream` between stages |
| **Agent system** | in-process bus (`pyee`) for tool/message events; broker across agents |
| **Voice runtime** | in-process async bus — audio frames and VAD as events, low latency |
| **CLI tool** | usually none — or a local in-process emitter |
| **System script** | none — or a thin outbox relay |
| **Evaluation harness** | event stream of runs; replay for deterministic re-eval |
| **Library** | builtins only (frozen events, `asyncio.Queue`); force no broker dep |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `asyncio.Queue` · frozen dataclasses | in-process bus + event values (builtin) | a single process; start here | stdlib |
| `faststream` | async service framework over Kafka/NATS/RabbitMQ/Redis/MQTT; DI, AsyncAPI, in-memory tests | producers/consumers across a broker | Apache-2.0, ag2ai — FastAPI-style |
| `eventsourcing` | aggregates, event store abstraction, projections, snapshots | the event-sourcing / CQRS path in Python | BSD-3, pyeventsourcing |
| `KurrentDB` (`kurrentdbclient`) | purpose-built event store (was EventStoreDB) | a dedicated append-only log with subscriptions | server + gRPC client; Postgres/Kafka are the alternatives |

A **job** (one consumer, retries, a deadline) is not an event: it goes to a job queue — `awa` on Postgres, whose transactional enqueue is the outbox, no relay → `sys-gen-scaling`. In-process event emitter → `pyee` (async) or `blinker` (signals) when a plain `asyncio.Queue` is too bare. Event wire schema + evolution → Avro/Protobuf/JSON Schema with a registry; the event *models* are `msgspec`/pydantic → `lang-py-datamodel`.

**Never:** publish straight to a named handler (defeats decoupling) · a broker where an in-process bus suffices · a non-idempotent consumer under at-least-once · event sourcing for plain CRUD · a breaking change to a persisted event schema.

## Testing

`pytest` + `faststream` `TestBroker` (in-memory, no real broker). Assert idempotency (redeliver an event, state unchanged), out-of-order tolerance, and dead-letter routing. For sourcing: fold a known event stream to expected state, and round-trip through an upcaster. Live-broker tests marked slow and opt-in.
