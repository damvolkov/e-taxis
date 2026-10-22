---
name: conc-py-async
description: "Python: concurrency inside one process — event loop, TaskGroup, Semaphore/Queue, IO- vs CPU-bound, threads vs processes. Use when work blocks the loop or needs offloading. Not replicas or queues."
metadata:
  family: design
---

# conc-py-async

Concurrency inside one process: run many things at once without blocking, and pick the right tool for the workload. Async-first. Owns the concurrency model and the IO-vs-CPU decision. Not here: async iteration and stream shape (`para-py-iteration`), cancellation and resource cleanup (`lang-py-lifecycle`), complexity profiling (`algo-py-core`), horizontal scaling and queues (`sys`). The stack every example draws on → `references/lib.md`.

## Rules

1. **The loop is cooperative — never block it.** One sync call (CPU work, `time.sleep`, blocking IO) freezes every task. All I/O is async; anything blocking is offloaded (rule 5).
2. **Structured concurrency, no orphan tasks.** `asyncio.TaskGroup` owns its children and propagates errors; `gather` for fixed fan-out, `as_completed` for results as they land. Never bare `create_task` fire-and-forget. Cancellation/cleanup semantics → `lang-py-lifecycle`. → `references/structured.md`
3. **Bound every concurrency.** Unbounded fan-out exhausts sockets and memory. Gate with `Semaphore`/`BoundedSemaphore` (or `anyio.CapacityLimiter`); a producer/consumer over `asyncio.Queue(maxsize=…)` gives backpressure — the CSP channel `para-py-iteration` defers here.
4. **Classify IO-bound vs CPU-bound before choosing a tool.** IO-wait dominates → async, or threads for blocking libs; CPU-time dominates → processes. Measure first with the profilers in `algo-py-core`; don't parallelize on a guess. → `references/decision.md`
5. **Offload by workload.** `asyncio.to_thread` / `run_in_executor(ThreadPoolExecutor)` for blocking IO; `ProcessPoolExecutor` / `multiprocessing` for CPU; never CPU work on the loop. Mind pickle cost across processes — pass references, not big payloads. → `references/offload.md`
6. **Know the GIL.** Threads do not parallelize pure-Python CPU under the GIL (free-threading 3.13t/3.14t lifts it — not yet the default); for CPU today, use processes. This is **vertical** scaling: all cores of one machine. → `references/offload.md`
7. **Scaling has two planes — solve each concern at its cheapest one.** Vertical (cores/threads/processes) is this skill; horizontal (replicas, queues, load balancers, Kubernetes) is infrastructure → `sys`. Don't build heavy in-process core management for a service that scales out on small nodes, nor put in the backend what a proxy or the platform resolves (rate limits, load spread).

## Sample

```python
import asyncio

async def fetch_all(urls: list[str], fetch, limit: int = 10) -> list[Response]:
    """Bounded concurrent fan-out — at most `limit` in flight, all-or-error via the group."""
    sem = asyncio.Semaphore(limit)
    async def guarded(u: str) -> Response:
        async with sem:                      # the gate: never more than `limit` concurrent
            return await fetch(u)
    async with asyncio.TaskGroup() as tg:    # structured: a failure cancels the siblings
        tasks = [tg.create_task(guarded(u)) for u in urls]
    return [t.result() for t in tasks]
```

`TaskGroup` owns the tasks and the error propagation; the `Semaphore` bounds concurrency. Unbounded `gather` over thousands of URLs would open thousands of sockets at once.

## References

- `references/decision.md` — IO-bound vs CPU-bound classification, the decision table, measuring which one you have
- `references/structured.md` — TaskGroup, gather vs as_completed, Semaphore, Queue producer/consumer, timeouts
- `references/offload.md` — threads vs processes, the GIL, free-threading, executors, pickle and shared state
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the works this domain leans on
- `references/lib.md` — the stack: `asyncio`, `anyio`, `concurrent.futures`/`multiprocessing`, `uvloop`
