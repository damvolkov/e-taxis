# lib — the core algorithmic stack

What to reach for when sorting, searching, hashing, selecting or applying a paradigm. Reach order: **builtins → `sortedcontainers` (mutable ordered) → `numpy`/`polars` (mass)**. Algorithms are CPU-bound; offload heavy work, don't reimplement it async. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The base-algorithm stack × the nine software categories.

| Category | Core stack |
|---|---|
| **API service** | builtins; `asyncio.PriorityQueue` for cross-task scheduling |
| **Async worker** | builtins; `heapq`/`asyncio.PriorityQueue` for job priority |
| **ML pipeline** | builtins for glue; `numpy`/`polars` for mass sort/unique/top-k |
| **Agent system** | builtins; `sortedcontainers` for a ranked set |
| **Voice runtime** | builtins only — `deque(maxlen)` ring buffers, no allocations on the audio path |
| **CLI tool** | builtins (`bisect`, `heapq`, `Counter`) |
| **System script** | builtins |
| **Evaluation harness** | builtins + `numpy.argpartition`; `polars` for batch ranking |
| **Library** | builtins only (no dependency on the consumer) |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `bisect` · `heapq` · `collections` · `functools` · `itertools` · `operator` | the base surface | always first | stdlib |
| `sortedcontainers` | `SortedList`/`SortedDict`/`SortedSet`, O(log n) | a **mutable** always-sorted collection | Apache-2.0, de-facto standard |
| `numpy` / `polars` | vectorized `sort`/`argpartition`/`unique`/`top_k` | selection/dedup over 10⁵⁺ items | BSD (C) / MIT (Rust) |
| `async-lru` | `lru_cache` for coroutines, dedups concurrent calls | memoize an async function | MIT, aio-libs (v2.0.4) |

**Never:** `x in list` in a loop · `list.pop(0)` for a queue · `sorted(...)[:k]` for small k · re-sort per key instead of a tuple key · `@cache` over an unbounded key space · reimplement `bisect`/`heapq`/`Counter`.

## Offload & profiling

Heavy sort/selection off the loop: `asyncio.to_thread` / `run_in_executor(ProcessPoolExecutor)`. Async memo: `async-lru`. Profile before/after: `timeit`, `cProfile`, `pyinstrument` (time); `memray` (memory). Process/thread details → `conc-py-async`.

## Testing

`pytest` (+ `anyio`), `hypothesis` against a naive reference (a sort vs `sorted`, a DP vs brute force), `pytest-benchmark` for regressions.
