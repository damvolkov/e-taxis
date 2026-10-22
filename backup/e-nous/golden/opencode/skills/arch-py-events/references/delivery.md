# delivery — guarantees, idempotency, ordering

The hard half of event-driven systems: what the transport promises, and what you must do because it cannot promise more.

## Delivery semantics

| Guarantee | Reality | What it costs you |
|---|---|---|
| at-most-once | fire and forget; may be lost | acceptable only for disposable signals |
| **at-least-once** | may be redelivered; never lost | the practical default — you handle duplicates |
| exactly-once | not real end-to-end; brokers approximate it per-partition with heavy machinery | do not design on it — make handlers idempotent instead |

Assume **at-least-once** and engineer for duplicates. "Exactly-once processing" is achievable as at-least-once delivery + idempotent handling — that is the honest framing.

## Idempotency

A handler applied twice equals once:

- **Idempotency key** — the event id; record processed ids, skip a repeat (dedup table with TTL).
- **Upsert / set semantics** — write the final value, not a delta; `set(k, v)` is idempotent, `increment(k)` is not.
- **Conditional apply** — apply only if a version/state guard holds (optimistic concurrency).

Non-idempotent effects (charge a card, send an email) need an idempotency key at the effect boundary, not just in the handler.

## Ordering

- Order is guaranteed only **within a partition/key**, never globally. Route events that must be ordered (same aggregate) to the same key.
- Cross-key ordering does not exist — design handlers to tolerate out-of-order arrival (version checks, buffering, or commutative operations).

## Not losing events

- **Outbox pattern** — write the event to an `outbox` table in the *same transaction* as the state change, then a relay publishes it. Removes the dual-write race (state committed, publish lost, or vice versa).
- **Dead-letter queue** — a message that keeps failing is moved aside after N attempts, so one poison event does not stall the stream; alert and inspect it, never drop it silently.
- **Consumer offsets / acks** — commit progress only after successful handling; a crash mid-handle redelivers, which idempotency makes safe.
- The async consumption itself — bounded concurrency, backpressure, structured cancellation — is `conc-py-async`.
