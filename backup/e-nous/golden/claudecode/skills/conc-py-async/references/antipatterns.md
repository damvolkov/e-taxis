# antipatterns — concurrency

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| blocking call on the loop (`time.sleep`, sync IO, CPU loop) | freezes every task | `asyncio.sleep` / `to_thread` / process pool |
| `create_task` fire-and-forget | orphan task, lost errors, leaks | `TaskGroup` owns it |
| unbounded `gather` over N items | thousands of sockets/tasks at once | `Semaphore` + `TaskGroup` |
| threads for pure-Python CPU | GIL serializes — no speedup, added overhead | `ProcessPoolExecutor` |
| processes for tiny tasks | pickle + IPC cost more than the work | run inline, or batch into fewer tasks |
| shipping large objects to a process | pickle dominates runtime | pass references/paths, partition at source |
| swallowing `CancelledError` | breaks cancellation | clean up and `raise` → `lang-py-lifecycle` |
| `yield` inside `TaskGroup`/`timeout` in an async generator | breaks cancel-scope nesting | consume inside, emit outside, or a queue |
| unbounded `Queue` producer/consumer | memory blows up under a slow consumer | `Queue(maxsize=…)` — backpressure |
| nested `wait_for` for deadlines | tangled cancellation | `asyncio.timeout()` |
| in-process core management on a horizontally-scaled service | contention, not throughput | scale out → `sys` |
| parallelizing before measuring | complexity with no proven win | profile first (→ `algo-py-core`) |
