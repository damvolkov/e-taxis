# structured — orchestration primitives

Every concurrent task has an owner that awaits it and propagates its error. No fire-and-forget.

## TaskGroup — the default

```python
async with asyncio.TaskGroup() as tg:        # 3.11+
    t1 = tg.create_task(a())
    t2 = tg.create_task(b())
# both awaited here; if one raises, the other is cancelled, errors surface as an ExceptionGroup
```

`TaskGroup` replaces bare `gather` for anything with side effects: it cancels siblings on failure and never leaks a task. Cancellation and cleanup semantics (CancelledError, shield, timeouts as cleanup) → `lang-py-lifecycle`.

## gather vs as_completed

- `asyncio.gather(*aws)` — fixed fan-out, results in argument order; `return_exceptions=True` to collect instead of fail-fast. Prefer `TaskGroup` when a failure should cancel the rest.
- `asyncio.as_completed(aws)` — iterate results as each finishes; use for streaming the fastest-first, or to apply a running timeout.

## Bounded concurrency

Unbounded fan-out is the most common async bug: thousands of tasks open thousands of connections.

```python
sem = asyncio.Semaphore(limit)               # or anyio.CapacityLimiter(limit)
async with sem:
    await work()                             # at most `limit` inside the gate
```

`BoundedSemaphore` also guards against an extra `release()`. A `CapacityLimiter` (anyio) is the same idea, portable across backends.

## Producer / consumer with backpressure

```python
q: asyncio.Queue[Item] = asyncio.Queue(maxsize=100)   # the bound IS the backpressure
async def producer():
    async for item in source():
        await q.put(item)                    # blocks when full — the producer is paced
async def consumer():
    while True:
        item = await q.get()
        try: await handle(item)
        finally: q.task_done()
```

A bounded `Queue` is the CSP channel `para-py-iteration` defers here: one task per stage, memory flat, the slow stage sets the pace. `await q.join()` waits for the backlog to drain.

## Timeouts

`async with asyncio.timeout(5):` (3.11+) scopes a deadline over a whole block; `asyncio.timeout_at` for an absolute one. Never nest `wait_for`. Deadline-as-cleanup detail → `lang-py-lifecycle`.
