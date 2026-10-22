# Async lifecycle

Async context managers, `AsyncExitStack`, cancellation and async generators. Structured concurrency itself — `TaskGroup` as an orchestration primitive, orphan tasks, `gather`, locks — is → `conc-py-async`; here it appears only where it touches cleanup.

## Async context managers

```python
@asynccontextmanager
async def session():
    s = await connect()
    try:
        yield s
    finally:
        await s.close()

async with AsyncExitStack() as stack:
    a = await stack.enter_async_context(session())
    stack.push_async_callback(flush)
    b = stack.enter_context(open("x"))       # sync and async mix in one stack
```

## Cancellation — the critical rule

- `CancelledError` is a `BaseException` (3.8+), so `except Exception` does not catch it — correct.
- **Never swallow it.** If you catch it, clean up and `raise`.
- An `await` in `finally` can itself be cancelled. Protect critical cleanup:

```python
finally:
    await asyncio.shield(conn.close())       # or a bounded timeout inside the shield
```

- Timeouts: `async with asyncio.timeout(5):` (3.11+), not nested `wait_for`. It turns cancellation into `TimeoutError` inside its scope only.

## Async generators

Finalization is not deterministic: `aclose()` is not called when you leave the `async for`.

```python
async with aclosing(stream()) as it:
    async for item in it:
        if done(item): break
```

Never `yield` inside a `TaskGroup` or `timeout` within an async generator — it breaks the cancellation-scope nesting. Consume inside, emit outside, or use a queue.

## Blocking work in async

`await asyncio.to_thread(fn, *args)` for one-off blocking IO. Never `time.sleep`, heavy file IO or CPU-bound work directly on the loop.

## Antipatterns

| ❌ | ✅ |
|---|---|
| `except asyncio.CancelledError: pass` | cleanup + `raise` |
| `create_task` fire-and-forget | `TaskGroup` → `conc-py-async` |
| nested `wait_for` | `asyncio.timeout()` |
| abandoned async generator | `aclosing` |
