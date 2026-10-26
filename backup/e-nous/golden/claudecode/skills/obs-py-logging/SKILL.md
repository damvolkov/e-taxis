---
name: obs-py-logging
description: "Python: structured logging — log events + dynamic kwargs, contextvars, PROD JSON vs DEV text, cheap level filtering, non-blocking handlers. Use when adding or configuring logs. Not naming or layout."
metadata:
  family: quality
---

# obs-py-logging

A log line is a queryable event, not a sentence. Emit an event name plus structured fields; render them as JSON in prod and as ordered flat text in dev, from one switch. Owns application logging. Config values (env, level) come from settings → `arch-py-hexagonal`; a slow sink is offloaded → `conc-py-async`; tracing and telemetry are a separate `obs` concern. The stack → `references/lib.md`.

## Rules

1. **Log events, not strings.** `log.info("order_placed", order_id=oid, total=cents)` — an event name and structured kwargs, never an f-string message. The kwargs are the data; each line is a record you can filter and query.
2. **One `setup()` at startup; `get_logger()` everywhere else.** Configure structlog once at the composition root, before any logger binds (env, level, stream); modules just call `structlog.get_logger()`. A library never calls `setup()` — the app owns configuration. → `references/setup.md`
3. **Two renderers, one env switch.** PROD → `JSONRenderer` with the msgspec (C) serializer and `BytesLoggerFactory`. DEV/LOCAL → the flat house renderer: timestamp, level, event, then `key: value` fields. ANSI only on a TTY, never into a pipe or file. → `references/renderers.md`
4. **Bind context, don't thread it.** `structlog.contextvars.bind_contextvars(request_id=…)` sets fields once and every log in that async task carries them — contextvars propagate across `await`, so it is async-safe; `log.bind()` for a local child logger. → `references/context.md`
5. **Filter cheap, never block the log path.** `make_filtering_bound_logger(level)` drops sub-level events before formatting; `cache_logger_on_first_use`; the sink is fast stdout. A remote or slow sink is queued or offloaded, never awaited inline. → `conc-py-async`
6. **Config is a contract; `print` is banned.** Level, env and format come from `pydantic-settings`, never `os.environ`; `print()` is unstructured, unleveled and unroutable. → `arch-py-hexagonal`
7. **Errors carry the exception.** `log.error("charge_failed", order_id=oid, exc_info=True)` so `format_exc_info` renders the traceback; add `stack_info=True` for the call site without an exception. → `references/renderers.md`

## Sample

```python
import structlog
from myapp.core.logger import setup
from myapp.settings import settings as st

setup(env=st.ENV, level=st.LOG_LEVEL)                    # once: PROD → JSON (msgspec), DEV → flat text

log = structlog.get_logger()
structlog.contextvars.bind_contextvars(request_id=rid)   # async-safe, carried across every await
log.info("order_placed", order_id=oid, total=cents)      # event + dynamic kwargs, not an f-string
try:
    charge(oid)
except PaymentError:
    log.error("charge_failed", order_id=oid, exc_info=True)   # exception attached, not stringified
```

`setup` runs once; `bind_contextvars` threads `request_id` through the whole task without passing it; every call is an event with its own fields.

## References

- `references/setup.md` — the one-time configure: shared processors, filtering wrapper, per-env factory, where setup lives
- `references/renderers.md` — PROD JSON (msgspec, BytesLogger) vs DEV flat renderer, key order, ANSI-on-TTY, exception rendering
- `references/context.md` — dynamic kwargs, `bind_contextvars` vs `bind`, async-safety, correlation/request ids
- `references/lib.md` — the stack: `structlog`, `msgspec`, `rich`, and the stdlib `logging` backend
