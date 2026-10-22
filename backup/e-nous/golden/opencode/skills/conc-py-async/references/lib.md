# lib — the concurrency stack

What to reach for to run work concurrently in one process. Reach order: **builtin `asyncio` → `anyio` (multi-backend) → builtin `concurrent.futures`/`multiprocessing` (offload) → `uvloop` (faster loop)**. Pooled resources (HTTP/DB clients), retries and servers live behind a scope → `lang-py-lifecycle`, not here. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The concurrency stack × the nine software categories.

| Category | Concurrency stack |
|---|---|
| **API service** | `asyncio` + `TaskGroup`; `uvloop`; `to_thread` for blocking deps |
| **Async worker** | `asyncio` `Queue`/`Semaphore`; `ProcessPoolExecutor` for CPU jobs |
| **ML pipeline** | `to_thread` for GIL-releasing NumPy/Polars; `ProcessPoolExecutor` for pure-Python CPU |
| **Agent system** | `asyncio` `TaskGroup` for concurrent tool calls, `Semaphore`-bounded |
| **Voice runtime** | `asyncio` streams; `to_thread` for device IO; `anyio.CapacityLimiter` |
| **CLI tool** | `concurrent.futures` pools in a `with`; `asyncio.run` for async subcommands |
| **System script** | `concurrent.futures`/`multiprocessing` for fan-out; `subprocess` |
| **Evaluation harness** | `TaskGroup` for parallel runs; `ProcessPoolExecutor` for heavy scoring |
| **Library** | `anyio` (backend-agnostic) or plain `asyncio`; no loop assumptions |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `asyncio` | event loop, `TaskGroup`, `Queue`, `Semaphore`, `to_thread`, `gather` | default for all in-process concurrency | stdlib (3.11+ for `TaskGroup`/`timeout`) |
| `anyio` | structured concurrency over asyncio/trio; `CapacityLimiter`, `to_thread`/`to_process` | backend-agnostic code (libraries, ASGI internals) | MIT, mature |
| `concurrent.futures` · `multiprocessing` | Thread/Process pools, real CPU parallelism | offload blocking IO (threads) or CPU (processes) | stdlib |
| `uvloop` | libuv drop-in event loop, faster IO | IO-heavy async server | MIT, C/Cython (`rloop` = Rust, experimental) |

Free-threading (3.13t/3.14t, PEP 703) removes the GIL — reassess the process-pool choice when it is your runtime.

**Never:** block the loop · `create_task` without an owner · unbounded `gather` · threads for pure-Python CPU · pickle large payloads across processes · re-list pooled clients/retries here (→ `lang-py-lifecycle`).

## Testing

`pytest` + `anyio` (or `pytest-asyncio`). Test bounded concurrency actually bounds (assert peak in-flight ≤ limit), cancellation propagates, and a producer/consumer drains. `pytest-benchmark` only for a measured throughput claim. `pytest-stress` (mandatory-recommended, → `test-py-tdd`) loops the suite for a time box (`pytest --seconds 60`) — races and intermittent deadlocks only repeat runs surface.
