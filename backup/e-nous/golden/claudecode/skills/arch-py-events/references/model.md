# model — events, commands, envelopes

The vocabulary decides the architecture. Get the three distinctions right first.

## Event vs command vs query

| Kind | Tense | Meaning | Can be rejected? | Fan-out |
|---|---|---|---|---|
| **Command** | imperative (`PlaceOrder`) | a request to change state | yes — the handler may refuse | one handler |
| **Event** | past (`OrderPlaced`) | a fact that already happened | no — it is history | many subscribers |
| **Query** | interrogative (`GetOrder`) | a request to read | — | one handler, no effect |

A command that has run *produces* events. Never phrase an event as a command (`PlaceOrder` as a stored event is a category error) — an event is immutable history; you cannot reject the past.

## Events are values

Model each as a frozen sum-type variant — the typed-value design is `arch-py-adt`. Immutable, serializable, inspectable; that is what makes a queue, replay, audit and undo possible. Give the whole set a `type OrderEvent = ...` union so consumers `match` exhaustively (`assert_never` → `lang-py-typing`).

## The envelope

The payload is the fact; the envelope is the metadata every event carries, separate from the domain fields:

- **event id** — unique, for idempotency and dedup.
- **timestamp** — when it happened (event time), distinct from processing time.
- **type + version** — for routing and schema evolution.
- **causation id** — the command/event that caused this one.
- **correlation id** — the workflow/request the whole chain belongs to (tracing).

Causation + correlation are what let you reconstruct *why* a chain ran, not just *what* ran.

## Thin event vs event-carried state transfer

- **Thin (notification)** — `OrderPlaced{order_id}`: small, but the consumer must call back to read details (coupling, load).
- **Event-carried state transfer** — `OrderPlaced{order_id, items, total, ...}`: the consumer needs no callback, at the cost of a larger event and duplicated data.

Choose per consumer need; carry the state a subscriber would otherwise have to fetch, no more. Fat events that carry the whole aggregate leak the write model into every consumer.
