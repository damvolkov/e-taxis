# context — dynamic fields, bound once

Two ways to attach fields, plus the base call. All three are "dynamic kwargs" — structlog never needs a fixed schema.

## Per-call kwargs

```python
log.info("cache_miss", key=key, plane="process")   # fields for this one event
```

The default and simplest: any keyword becomes a field. The event name is a stable string (grep/aggregate on it); the kwargs are the variable data.

## `bind` — a child logger

```python
log = structlog.get_logger().bind(component="ingest")   # every call on this logger carries component
log.info("batch_started", size=n)
```

`bind()` returns a new logger with those fields baked in — good for a component or a loop that logs many related events. Local, explicit, passed around like any object.

## `bind_contextvars` — ambient, async-safe

```python
structlog.contextvars.bind_contextvars(request_id=rid, tenant=tid)   # set once per task
...                                                                   # every log in this task, at any depth, carries them
structlog.contextvars.clear_contextvars()                            # at the task boundary
```

- Backed by `contextvars`, which **propagate across `await`** and are isolated per task — so a request/message handler binds `request_id` once and every downstream log includes it, with no threading of arguments and no cross-task leakage.
- `merge_contextvars` (first in the processor chain) folds them into each event.
- Clear or reset at the boundary (middleware, message handler) so the next request starts clean; a bound-and-forgotten contextvar bleeds into the next unit of work.

## Correlation and causation

For distributed flows, bind a **correlation id** (the whole request/workflow) and a **causation id** (the immediate cause) as contextvars at the entry point; they then ride every log line and, propagated as event fields, stitch a trace across services (the event-envelope side → `arch-py-events`).

## When to use which

Per-call for one-off fields · `bind()` for a component/loop's shared fields · `bind_contextvars` for request/task-scoped ambient fields that must reach code that never sees them.
