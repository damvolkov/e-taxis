# offload — threads, processes, the GIL

The loop must never run blocking or CPU-heavy code. Move it off, by workload.

## Blocking IO → a thread

```python
result = await asyncio.to_thread(blocking_call, *args)        # one-off, 3.9+
# or a shared pool:
loop.run_in_executor(thread_pool, blocking_call, *args)
```

Threads are right when the call *waits* (a blocking DB driver, `requests`, disk): the GIL is released during the wait, so other threads and the loop proceed.

## CPU-bound → a process

```python
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor() as pool:
    results = await loop.run_in_executor(pool, cpu_heavy, chunk)
```

Processes give real parallelism for pure-Python CPU because each has its own interpreter and GIL. Costs: startup, and every argument/result is **pickled** across the boundary — pass references or file paths, partition the data at the source, never ship large objects.

## The GIL and free-threading

- One GIL per interpreter serializes pure-Python bytecode: N threads doing Python CPU run as fast as one. Threads help only when the work *waits* or *releases the GIL*.
- **GIL-releasing** work (NumPy, Polars, `hashlib`, compiled extensions, blocking IO) *does* parallelize on threads — prefer threads there, no pickling.
- **Free-threading** (PEP 703, 3.13t/3.14t builds) removes the GIL; pure-Python threads then parallelize. It is not the default runtime yet — target it explicitly and reassess `ProcessPoolExecutor` choices when it is available.

## anyio — portable structured concurrency

`anyio` runs the same code on asyncio or trio: `anyio.to_thread.run_sync`, `anyio.to_process.run_sync`, `CapacityLimiter`, task groups. Reach for it when the code must be backend-agnostic (libraries, FastAPI/Starlette internals).

## uvloop — a faster loop

`uvloop` (libuv) is a drop-in replacement for the default event loop, meaningfully faster on IO-heavy servers: `uvloop.install()` or `asyncio.run(main(), loop_factory=uvloop.new_event_loop)`. `rloop` (Rust) is the experimental alternative — not yet stable.
