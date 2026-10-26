# decision — IO-bound vs CPU-bound, and which model

The whole choice hinges on **where the time goes**. Classify first, then pick the model. Never parallelize on a guess — measure.

## Classify the workload

- **IO-bound** — the task spends most of its time *waiting* (network, disk, database, subprocess). CPU sits idle. Symptoms: low CPU utilization while the task runs, latency dominated by round-trips.
- **CPU-bound** — the task spends most of its time *computing* (parsing, math, compression, serialization). Symptoms: one core pinned at 100%, latency scales with data size, no waiting.
- **Mixed** — split it: do the IO async, offload the CPU stage to a process.

Measure with the profilers owned by `algo-py-core` (`cProfile`/`pyinstrument` for where time goes, `py-spy`/`py-spy dump` for a live process, wall-clock vs CPU-time gap for IO-wait). A large wall-clock − CPU-time gap ⇒ IO-bound; wall-clock ≈ CPU-time on one core ⇒ CPU-bound.

## The decision table

| Workload | Model | Tool |
|---|---|---|
| IO-bound, async-native libs | single-loop concurrency | `asyncio` + `TaskGroup`, bounded by `Semaphore` |
| IO-bound, blocking libs only | threads | `asyncio.to_thread` / `ThreadPoolExecutor` |
| CPU-bound, pure Python | processes | `ProcessPoolExecutor` / `multiprocessing` |
| CPU-bound, releases the GIL (NumPy, Polars, compiled) | threads are fine | `to_thread` — the C code runs in parallel |
| CPU-bound, irreducible Python loop | JIT then offload | `numba` (→ `algo-py-numeric`) in a process/thread |
| Mixed | split | async IO + offloaded CPU stage |
| Small / one-shot | none | just call it — concurrency has overhead |

## Don't parallelize when

- The work is trivial: task setup, pickling and IPC cost more than the work saved.
- It is CPU-bound and you reach for threads: the GIL serializes pure-Python CPU — no speedup, added overhead.
- The bottleneck is elsewhere: a slow database or network is not fixed by more local workers.
- It scales out horizontally already: adding in-process parallelism to a service deployed as many small replicas adds contention, not throughput (→ rule 7, `sys`).

## Vertical ceiling → horizontal

Vertical scaling ends at the machine: cores, RAM, one loop's throughput. Past that, the answer is not a cleverer in-process scheme but another plane — replicas behind a balancer, a work queue, partitioned load. That is `sys`, and it is usually cheaper than the last increment of in-process complexity.
