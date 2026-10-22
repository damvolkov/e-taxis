---
name: arch-py-events
description: "Python: event-driven architecture — events/commands as values, pub/sub, at-least-once delivery, idempotency, sourcing, CQRS, sagas. Use when components react to facts, not direct calls."
metadata:
  family: design
---

# arch-py-events

Structure the system so components emit facts and react to them, decoupled in time and identity: the producer publishes an event and never knows who consumes it. Owns the event-driven paradigm — the shape of the system, not its plumbing. Transport and brokers → `sys-gen-scaling`; async handlers, the loop and backpressure → `conc-py-async`; the event/command as a typed value → `arch-py-adt`; the stream pipeline shape → `para-py-iteration`. The bus and store stack → `references/lib.md`.

## Rules

1. **An event is a fact, past tense; a command is an intent.** `OrderPlaced` (happened, immutable) vs `PlaceOrder` (requested, may be rejected) — both frozen sum-type variants with an envelope (id, time, causation/correlation). The type is `arch-py-adt`. → `references/model.md`
2. **Publish to a topic, not to a handler.** The producer emits to a bus; consumers subscribe. Coupling in time, identity and deployment is severed — that severance is the whole point, and its cost is eventual consistency. → `references/patterns.md`
3. **Assume at-least-once; make every handler idempotent.** Networks redeliver and replay; a handler applied twice must equal once — idempotency key, upsert, dedup. Order holds per partition/key, never globally. → `references/delivery.md`
4. **Never lose an event across a boundary.** Persist-then-publish via the outbox pattern; dead-letter the poison message instead of blocking the stream; the failure of one consumer is not the failure of the producer. → `references/delivery.md`
5. **Event-source only when the log is the truth.** Persist the event stream as source of truth and fold it to state; CQRS splits the write model (events) from read projections. Earn it with audit, replay or temporal queries — otherwise store state. → `references/sourcing.md`
6. **Version events from the first release.** A persisted event outlives the code that wrote it: additive evolution and upcasters only, never a breaking change to a stored schema. → `references/sourcing.md`
7. **Coordinate multi-service flows as sagas, not distributed transactions.** A workflow spanning services is choreography (events) or an orchestrator, each step with a compensating action; there is no two-phase commit here. → `references/patterns.md`

## Sample

```python
from dataclasses import dataclass
from typing import assert_never

@dataclass(frozen=True, slots=True)
class OrderPlaced:                       # a fact — past tense, immutable
    order_id: str
    total: int

@dataclass(frozen=True, slots=True)
class OrderCancelled:
    order_id: str

type OrderEvent = OrderPlaced | OrderCancelled

def project(ledger: Ledger, event: OrderEvent) -> Ledger:
    """Fold an event into the read model — idempotent, so replay and redelivery are safe."""
    match event:
        case OrderPlaced(order_id, total): return ledger.set(order_id, total)   # upsert: twice == once
        case OrderCancelled(order_id):     return ledger.remove(order_id)
        case _:                            assert_never(event)
```

The event is a frozen value; the projection is a pure fold with exhaustive `match`; the upsert makes it idempotent. State is derived, never the truth.

## References

- `references/model.md` — events vs commands, past-tense naming, the envelope, event-carried state vs thin events
- `references/patterns.md` — bus/topic, choreography vs orchestration, sagas and compensation, mediator vs broker
- `references/delivery.md` — delivery semantics, idempotency, ordering/partitioning, outbox, dead-letter
- `references/sourcing.md` — event sourcing, CQRS, projections, snapshots, schema versioning and upcasters
- `references/lib.md` — the stack: async framework, in-process bus, event store, serialization/registry
