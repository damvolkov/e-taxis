# Errors

Rust's `Result` + `?`: a failure propagates by default; you catch it only where you know what to do.

## try / except / else / finally

```python
try:
    conn = acquire()          # only the line that raises the expected error
except TimeoutError as e:
    raise ServiceUnavailable("db") from e   # chain the cause
else:
    use(conn)                 # runs only if no exception; its errors are not caught above
finally:
    cleanup()                 # always: on return, break, exception
```

- **Minimal `try`.** Only the failing line; the rest in `else`, so no unrelated bug is masked.
- **Specific excepts.** Never `except:` or `except BaseException`. `except Exception` only at a boundary (main, HTTP handler, worker) with log + re-raise or a controlled response.
- **`raise ... from e`** preserves the cause; `from None` only when the cause is intentional noise.
- **`e.add_note("ctx")`** (3.11+) adds context without wrapping the exception.
- **Never `return`/`break`/`continue` in `finally`** — it swallows the in-flight exception. `SyntaxWarning` from 3.14 (PEP 765).
- **Bare `raise`** inside `except` re-raises with the traceback intact.

## Cost — EAFP vs LBYL

Entering a `try` is zero-cost (CPython 3.11+); the cost is *raising* — building the object, the traceback, the unwinding.

| Failure is | Use | Why |
|---|---|---|
| rare | EAFP — `try: d[k]` | the happy path pays nothing |
| frequent | LBYL — `if k in d` | avoid the raise cost in a hot loop |
| a race window | EAFP | LBYL's check-then-use is a TOCTOU on files |

Hot loop with frequent failure → non-raising APIs: `dict.get`, `getattr(o, n, None)`, `str.isdigit()`.

## Aggregate — ExceptionGroup / except*

```python
try:
    async with asyncio.TaskGroup() as tg: ...
except* ConnectionError as eg:       # handles the subgroup; the rest propagates
    for e in eg.exceptions: log(e)
```

`ExceptionGroup` aggregates parallel-task or validation failures. `except*` never mixes with plain `except` in one block.

## Hierarchy

```python
class AppError(Exception): ...
class NotFound(AppError): ...
class Conflict(AppError): ...
```

One root per library or domain. The caller catches `AppError` at the boundary, the specific type where it can act.

## Antipatterns

| ❌ | ✅ |
|---|---|
| `try: ... except: pass` | `with suppress(SpecificError):` |
| `except Exception as e: raise MyError(str(e))` | `raise MyError(...) from e` |
| `try` around 30 lines | minimal `try` + `else` |
| `return` in `finally` | return outside the block |
| exceptions for control flow in a hot loop | `dict.get` / LBYL |
| ignoring a `TaskGroup`'s `ExceptionGroup` | `except*` |
