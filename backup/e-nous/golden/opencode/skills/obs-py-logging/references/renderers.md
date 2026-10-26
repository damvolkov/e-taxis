# renderers — PROD JSON, DEV flat

One env switch picks the renderer and the logger factory. The processor chain upstream is identical.

## PROD — JSON, machine-first

The serializer is C-backed `msgspec.json.encode`; structlog's `default` arg becomes msgspec's `enc_hook`:

```python
def encode_json(event_dict, default=None) -> bytes:
    return msgspec.json.encode(event_dict, enc_hook=default)
```

- Renderer: `JSONRenderer(serializer=encode_json)`.
- Factory: `BytesLoggerFactory(file=stream.buffer)` — msgspec emits bytes, so the factory writes to the binary buffer, not the text stream.
- One JSON object per line (JSONL); every field is flat and queryable by a log pipeline. No colors, no alignment — machines read it.
- msgspec over stdlib `json`: C speed, and the `enc_hook` serializes dataclasses, `msgspec.Struct` and enums.

## DEV / LOCAL — flat, human-first

The house renderer prints one flat line per event — `ts | LEVEL | event || k: v` — following these rules:

- **Priority order** — a configured `order` of keys renders first (`request_id`, `user_id`, say); the rest sort. The important fields never move around.
- **Level column** — fixed width, colored per level.
- **ANSI only on a TTY** — gate on `colors and stream.isatty()`. Piped to a file or another process, the text carries no escape codes.
- Built on `PrintLoggerFactory`, which writes text. Optional: `rich` for prettier tracebacks and console tables in dev.

## Exceptions

- A log call inside an `except` block, or `exc_info=True`, puts the live exception in the event.
- `format_exc_info` renders it into an `exception` field, printed last.
- `stack_info=True` → the call-site stack without an exception, for "how did we get here" traces.
- PROD: the traceback is a JSON string field. DEV: it prints below the line.
- Never pre-format a traceback into the event message — let the processor render it.
