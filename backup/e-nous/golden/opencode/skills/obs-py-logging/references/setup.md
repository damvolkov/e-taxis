# setup — configure once, at the root

structlog is configured a single time, at process startup, before any logger is bound. Put the call at the composition root (the app's `main`/lifespan), driven by settings.

```python
def setup(*, env: str, level: int, stream: TextIO = sys.stdout, **renderer_kwargs) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,      # pull bound contextvars into the event
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,          # render exc_info into `exception`
    ]
    match env.lower():
        case "prod":
            renderer = structlog.processors.JSONRenderer(serializer=encode_json)   # msgspec
            factory = structlog.BytesLoggerFactory(file=stream.buffer)             # msgspec emits bytes
        case "dev" | "local":
            renderer = ELogger(stream=stream, **renderer_kwargs)                    # flat text
            factory = structlog.PrintLoggerFactory(file=stream)
        case unknown:
            raise ValueError(f"unknown env {unknown!r}")
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),   # drop sub-level cheaply
        logger_factory=factory,
        cache_logger_on_first_use=True,                              # bind once, reuse
    )
```

## The processor chain

Order matters — each processor mutates the event dict in turn, the renderer is last:

1. `merge_contextvars` — fold in whatever `bind_contextvars` set for this task.
2. `add_log_level` — the `level` field.
3. `TimeStamper(iso, utc)` — a `timestamp` field; ISO + UTC so logs sort and compare across hosts.
4. `StackInfoRenderer` + `format_exc_info` — turn `stack_info=True`/`exc_info=True` into rendered fields.
5. the **renderer** (JSON or flat) — terminal, produces the line.

## Where it lives

- App: call `setup(env=st.ENV, level=st.LOG_LEVEL)` in the entrypoint/lifespan, before serving. Settings from `pydantic-settings` → `arch-py-hexagonal`.
- **Library**: never call `setup()` — a library only `structlog.get_logger()`s and lets the host app configure. Configuring inside a library hijacks the consumer's logging.
- `cache_logger_on_first_use=True` means the bound logger is frozen on first use; call `setup` before the first `get_logger().info(...)`, not after.
