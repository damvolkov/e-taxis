# sourcing — event sourcing, CQRS, versioning

The deep end: make the event log the source of truth. Powerful and costly — reach for it only when the log itself earns its keep.

## Event sourcing

Instead of storing current state, store the ordered stream of events that produced it; **state is a left fold over the stream**:

```python
state = reduce(apply, events, initial)   # replay = re-derive; no data lost, ever
```

- **Append-only** — events are immutable facts; you never update or delete, you append a corrective event.
- **Replay** — rebuild any past state, audit every change, debug by re-running history.
- **Snapshots** — fold is O(n) in stream length; periodically persist a snapshot and replay only events after it, so load stays bounded.

Adopt it for audit trails, temporal queries ("state as of T"), or domains where *why* matters as much as *what*. Reject it for simple CRUD — it adds real complexity (versioning, projections, eventual consistency) that plain state storage avoids.

## CQRS

Command Query Responsibility Segregation: the **write model** (validate a command, emit events) is separate from **read models** (projections shaped for queries). Events flow from write to read; a projection is a fold of the stream into a query-optimized view (`data-py-cache` / a table / a search index).

- The read side is eventually consistent — a projection lags the write by the propagation delay; the UI must tolerate it.
- CQRS does not require event sourcing (you can project from a state DB's change feed), but the two pair naturally.
- Multiple projections from one stream: a SQL view, a cache, an analytics rollup — each rebuilt by replaying events.

## Schema versioning

A persisted event outlives the code that wrote it, so its schema is a forever-contract:

- **Additive only** — add optional fields; never rename, retype or remove a field in place.
- **Upcasters** — a function that transforms a v1 event into v2 on read, so old events keep folding into new code.
- **Version in the envelope** — route each event to the right upcaster chain by `type + version`.
- A breaking change is a *new event type*, not a mutation of the old one; the old type stays readable forever.
