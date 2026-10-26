# lib — the iteration stack

The single authority on what to import for iteration, and what never to. Every example in this skill and its references draws from here. Order of reach: builtin / rust-backed → the async twin → the specialized library, and only when its shape is the point. Async is the default column; the sync builtin is the alternative when the source is already resident and nothing awaits. The async/sync split is drawn only where awaiting changes the answer.

## By software category

The matrix: the traversal stack (the skill's target) × the nine software categories. `⟳` = async default. The split is driven by whether the source is a live stream (async) or resident data (sync builtin).

| Category | Iteration stack |
|---|---|
| **API service** | `asyncstdlib` ⟳ — async streams end to end |
| **Async worker** | `asyncstdlib` ⟳; `anyiostream` ⟳ for inter-stage backpressure |
| **ML pipeline** | `asyncstdlib` ⟳ + `cytoolz`; materialize to `polars` for numeric mass |
| **Agent system** | `asyncstdlib` ⟳ |
| **Voice runtime** | `anyiostream` ⟳ — bounded channels, backpressure on realtime audio |
| **CLI tool** | builtin `itertools`/`functools` (resident, sync) |
| **System script** | builtin `itertools`/`functools` (resident, sync) |
| **Evaluation harness** | builtin `itertools` + `cytoolz`; `polars` for batch scoring |
| **Library** | builtin `itertools` (force no dep on the consumer); `asyncstdlib` only if the public API is async |

The rule underneath: **live stream → `asyncstdlib` (⟳); resident data → builtin `itertools`; heavy composition → `cytoolz`; numeric mass → vectorize with `polars`; realtime backpressure → `anyiostream`.** Category only selects which of these dominates.

## Libraries — what to reach for, and what not

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `itertools` · `functools` · `operator` · `heapq` | sync stdlib surface | source resident, nothing awaits | stdlib |
| **`asyncstdlib`** (`asl`) | async twin of itertools + functools + builtins + heapq + contextlib, loop-agnostic (asyncio/trio/any) | **default** whenever data is async and you are off anyio | MIT, py≥3.8 |
| `aioitertools` | stdlib names + signatures as async generators, asyncio-oriented | want the stdlib model with zero new surface, mixing resident lists + async streams | MIT, py≥3.9 |
| `anyio.itertools` · `anyio.functools` | async ops already shipped with anyio | already on anyio (FastAPI/httpx2/Starlette) — no new dependency | MIT, asyncio+trio |
| `aiostream` | `\|` pipe / `[]` slice / `+` Stream composition, single task | composition is the point, asyncio only | **GPL-3.0** — copyleft, clear before shipping |
| `anyiostream` | task-per-stage CSP: bounded channels, backpressure, fan-out, Ok/Err | true inter-stage concurrency | Apache-2.0, **alpha 0.0.1a0** — pin, py≥3.12 |
| more-itertools · cytoolz | after the stdlib + async surface is exhausted | `windowed`/`partition`/`unique_everseen`; cytoolz for non-adjacent C `groupby`/`pluck` | MIT |

**Decision:** builtin → `asyncstdlib` → `anyio` (if already on it) → `aiostream`/`anyiostream` (composition / concurrency).
**Never:** hand-write a traversal the stdlib already has · drain an async source to sync to reach `itertools` · ship `aiostream` in an `e-` project without clearing GPL-3.0 · treat `anyiostream` (alpha) as stable.

`asyncstdlib` is **async-neutral** — its functions accept sync iterables and sync callables too, so mixed sources compose with no coercion (a callable's result must be consistently sync or async). Its `reduce`/`lru_cache`/`cached_property` are the async-safe versions stdlib lacks — stdlib `lru_cache` caches the coroutine object, never its result. It **eagerly acloses** the iterators it drives: `asl.borrow` to skip that, `asl.scoped_iter` to guarantee it.

## Operators — async first, sync alternative

`asl.*` = `asyncstdlib`. **same** = the sync form is already correct over async data (pure work on resident values). **sync-only** = no async meaning.

### Builtins & terminals

| Operation | Async | Sync | Use |
|---|---|---|---|
| sum / min / max | `asl.sum/min/max` | `sum/min/max` | fold; async awaits each step |
| any / all | `asl.any/all` | `any/all` | short-circuit predicate over a stream |
| enumerate | `asl.enumerate` | `enumerate` | index a stream without a counter |
| zip | `asl.zip` | `zip` | parallel streams, stop at shortest |
| zip_longest | `asl.zip_longest` | `itertools.zip_longest` | parallel streams, pad with fillvalue |
| map / filter | `asl.map/filter` | `map/filter` | elementwise transform / keep predicate |
| collect | `asl.list(it)` | `list(it)` | drain to a concrete list at the boundary |
| next item | `await anext(it)` | `next(it)` | one item; async returns an awaitable |

### itertools

| Operation | Async | Sync | Use |
|---|---|---|---|
| chain / from_iterable | `asl.chain` | `itertools.chain` | concat; flatten one level without the outer list |
| islice | `asl.islice` | `itertools.islice` | window / head of a stream, no indexing |
| accumulate | `asl.accumulate` | `itertools.accumulate` | running totals, prefix ops |
| groupby | `asl.groupby` | `itertools.groupby` | **adjacent** runs only — sort first |
| pairwise | `asl.pairwise` | `itertools.pairwise` | consecutive pairs (deltas, transitions) |
| takewhile / dropwhile | `asl.*` | `itertools.*` | cut a stream on a predicate |
| filterfalse / compress | `asl.*` | `itertools.*` | negative filter / mask by selectors |
| starmap | `asl.starmap` | `itertools.starmap` | apply fn to already-unpacked tuples |
| tee | `asl.tee` | `itertools.tee` | two readers of one source — buffers, measure |
| count / cycle / repeat | `asl.*` | `itertools.*` | infinite sources, always paired with a cut |
| product / permutations / combinations | sync-only | `itertools.*` | combinatorics are in-memory and factorial/exponential |
| batched | sync-only | `itertools.batched` (3.12+) | fixed chunks; async: `islice` loop or aiostream `chunks` |

### heapq · functools · operator · collections

| Operation | Async | Sync | Use |
|---|---|---|---|
| merge | `asl.merge` | `heapq.merge` | merge pre-sorted streams |
| nlargest / nsmallest | `asl.nlargest/nsmallest` | `heapq.nlargest/nsmallest` | top-k without sorting everything |
| reduce | `asl.reduce` | `functools.reduce` | fold with no builtin terminal |
| cached_property | `asl.cached_property` | `functools.cached_property` | one-shot per instance |
| lru_cache / cache | `asl.lru_cache/cache` | `functools.lru_cache/cache` | **async needs `asl`** — stdlib caches the coroutine, not the result |
| partial | same | `functools.partial` | bind args instead of a lambda; wraps async fns fine |
| attrgetter / itemgetter / methodcaller | same | `operator.*` | C-level keys and mappers; name the intent |
| add / mul / eq / lt … | same | `operator.*` | `reduce` bodies instead of lambdas |
| Counter · deque(maxlen) · defaultdict · ChainMap | drain to fill | `collections.*` | terminal drain: `Counter([x async for x in xs])` |

## Paths & files — async first, sync alternative

Default to builtin `pathlib`/`open`: a one-shot `stat`, `exists` or small read should not pay an async wrapper — run it off the hot path or through `anyio.to_thread`. Reserve async I/O for throughput or genuine concurrency on real reads/writes.

| Lib | Shape | Backend | Reach for it when | License |
|---|---|---|---|---|
| `aiofile` | file I/O + low-level | **kernel AIO** — io_uring / libaio (Linux), thread / pure-Python fallback, auto-picked | peak file throughput on Linux; positional/batched I/O | Apache-2.0, py≥3.11 |
| `anyio.Path` | pathlib-shaped paths + file | worker threads | already on anyio; portable async pathlib | MIT |
| `aiopath` | full `AsyncPath` (subclass of `pathlib.Path`) | anyio threads; optional aiofile backend | want the pathlib API async, off anyio | LGPL-3.0, **stale (2023)** |
| `aiofiles` | file I/O only | worker threads | `aiofiles.open()` familiarity, low concurrency | thread-pool |
| `pathlib` (sync) | paths | sync | trivial / one-shot, or offloaded via `to_thread` | stdlib |

Benchmark truth (aiofile, 2026): **libaio** posts the lowest per-op latency at low concurrency; **io_uring** only pulls ahead once there is a batch to amortize; **aiofiles/aiomisc degrade under concurrency** (a single seek cursor serialized by a lock) while positional-I/O libs improve. io_uring/libaio cannot open special files (`/proc`, `/sys`, pipes) — switch to the thread context for those.

```python
from aiofile import async_open, AIOFile, Reader

async def lines(path):
    async with async_open(path) as f:                     # file-like; __aiter__ reads lines
        async for line in f:
            yield line

async with AIOFile(path, "rb") as f:
    async for chunk in Reader(f, chunk_size=64 * 1024):   # chunked
        ...
```

Glob async: `async for p in AsyncPath(d).glob("**/*")` (aiopath) or `anyio.Path` + `to_thread`. Always close a generator that holds a handle (`contextlib.aclosing`).

## Stack — async (first) · sync

The fixed summary: the import to reach for, by concern. Builtin / rust-backed always first.

| Concern | Async (first) | Sync |
|---|---|---|
| map · filter · zip · enumerate | `asl.*` | builtin |
| fold — sum/min/max/any/all/reduce | `asl.*` | builtin · `functools.reduce` |
| flatten · slice · group · window | `asl.*` | `itertools.*` |
| top-k · merge sorted | `asl.nlargest` · `asl.merge` | `heapq.*` |
| count · dedup · sliding window | `Counter` · `set` · `deque` | `Counter` · `set` · `deque` |
| keys & mappers | `operator.*` | `operator.*` |
| async-safe cache | `asl.lru_cache` · `anyio.functools` | `functools.lru_cache` |
| pipe composition | `aiostream` (GPL) | — |
| concurrent stages · backpressure | `anyiostream` (alpha) | — |
| paths & files | `aiofile` · `anyio.Path` | `pathlib` |
