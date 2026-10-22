# lib — the logging stack

What to reach for to log. Reach order: `structlog` (the engine) → `msgspec` (PROD JSON, C-backed) → `rich` (DEV console/tracebacks); stdlib `logging` is the backend structlog wraps and interops with. Config values come from settings, not here → `arch-py-hexagonal`. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The logging stack × the nine software categories. The engine is uniform; what varies is the context bound and where `setup` runs.

| Category | Logging stack |
|---|---|
| **API service** | `structlog`; `bind_contextvars(request_id)` in middleware; PROD JSON |
| **Async worker** | `structlog`; bind per message/task, clear at the boundary; PROD JSON |
| **ML pipeline** | `structlog` per stage; event = step, fields = metrics/shapes |
| **Agent system** | `structlog`; correlation/causation ids as contextvars → `arch-py-events` |
| **Voice runtime** | `structlog`, but keep the log path off the audio hot loop — offload the sink |
| **CLI tool** | `structlog` for logs; `rich` for user-facing console/tables (a different channel) |
| **System script** | `structlog`, DEV flat renderer to a TTY |
| **Evaluation harness** | `structlog`; structured events feed the eval record |
| **Library** | `structlog.get_logger()` only — **never** call `setup()`; the host app configures |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `structlog` | the engine: events, binding, contextvars, processor chain, renderers | all application logging | MIT — house pins `>=26.1` |
| `msgspec` | PROD JSON serializer (C), via the renderer's `enc_hook` | prod machine logs; also the event-model lib → `lang-py-datamodel` | BSD-3 (C), `>=0.21` |
| `rich` | DEV console, tables and pretty tracebacks | human-facing dev output and CLI (`cli` domain) | MIT, Textualize |
| `logging` | stdlib backend structlog wraps; third-party libs log through it | interop — route library logs into the same chain | stdlib |

The house's DEV renderer is a small custom `ELogger` (flat `ts | LEVEL | event || k: v`), not a library. Async offload of a slow sink → `conc-py-async`.

**Never:** `print()` for diagnostics · f-string log messages (put data in kwargs) · `os.environ` for config (use settings) · `setup()` inside a library · ANSI into a non-TTY · a blocking sink on the log path.

## Testing

`structlog.testing.capture_logs` asserts events and their fields without a real sink. Check the env switch (PROD emits parseable JSON, DEV emits the flat line), that `exc_info=True` attaches the exception, and that a bound contextvar appears on a downstream event.
