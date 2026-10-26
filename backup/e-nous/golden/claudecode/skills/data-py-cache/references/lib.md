# lib — the cache stack

Reach order in every cell: **builtin / Rust-backed → async twin → specialized library**. Four primaries, one per plane. All data measured **2026-09-17**; re-verify → `flow-gen-research`.

## Cache plane × software category

| Plane | API service | Async worker | ML pipeline | Agent system | CLI tool / script | Evaluation harness |
|---|---|---|---|---|---|---|
| **In-process, sync** | builtin `functools` | builtin `functools` | builtin `functools` | builtin `functools` | builtin `functools` | builtin `functools` |
| **In-process, async** | `async-lru` | `async-lru` | `async-lru` | `async-lru` | `async-lru` | `async-lru` |
| **In-process, bounded/TTL** | `cachebox` | `cachebox` | `cachebox` | `cachebox` | `cachebox` | `cachebox` |
| **Disk** | — | `cashews` (disk backend) | `cashews` (disk backend) | `cashews` (disk backend) | `diskcache` | `cashews` (disk backend) |
| **Shared** | `cashews` | `cashews` | `cashews` | `cashews` | — | `cashews` |
| **HTTP** | `hishel` | `hishel` | `hishel` | `hishel` | `hishel` | `hishel` |

Async / sync per primary: `cachebox` **same** (the decorator takes coroutines) · `async-lru` **async-only** · `cashews` **async-only** · `hishel` **same** (sync and async httpx/httpx2) · `wreq` **none** · `functools` **sync-only** — on an `async def` it caches the coroutine, not the result.

## The floor — builtin `functools`

Always the first reach, never a dependency. Three tools, three different jobs:

| | Holds | Bounded | Use for |
|---|---|---|---|
| `functools.cache` | in memory, process-wide | **no** — unbounded | pure functions over a provably small key space (enum, depth, config) |
| `functools.lru_cache(maxsize=N)` | in memory, process-wide | yes, LRU | the same, when the key space is not provably small |
| `functools.cached_property` | on the instance | per instance | a value computed once per object, dying with it |

No TTL, no eviction policy beyond LRU, no external backend, no async. The moment you need any of those, climb to a primary — do not reimplement them around `lru_cache`.

## The four

| Library | Version · release | Holds | Why this one |
|---|---|---|---|
| **`cachebox`** | 6.2.7 · 2026-09-04 · pushed 2026-09-15 · **0 open issues** | in-process, Rust | Rust/PyO3, completely thread-safe via a Rust mutex. Seven policies — `FIFOCache`, `LRUCache`, `LFUCache`, `RRCache`, `TTLCache`, `VTTLCache` and the base `Cache` — so TTL and per-entry expiry exist without leaving the process. The decorator takes coroutines, and it mitigates stampede with an internal lock. Post-1.0 and maintained at a clip: this is what `functools` grows into, and what satisfies the Rust-backed mandate over pure-Python `cachetools`. Python 3.10+. |
| **`async-lru`** | 2.3.0 · 2026-03-19 · pushed 2026-09-14 | in-process, async | `lru_cache` for coroutines — the thing stdlib does not have. It caches the **result**, dedups concurrent calls on the same key, and supports TTL. 37.3M downloads/month, `aio-libs`. Reach for it the moment the function you want to memoize is `async def`. |
| **`cashews`** | 7.5.0 · 2026-03-02 · pushed 2026-09-17 | shared, universal | The only one that meets the whole brief: **memory + Redis + DiskCache** behind one API, an abstract `Backend` (~25 methods) to write your own, **framework-agnostic** (FastAPI and Prometheus are optional contrib). Ships what you would otherwise hand-roll: anti-stampede (`early` / `soft` / `locked`), **invalidation by tag and by pattern**, rate limiting, circuit breaker, bloom filters. Async-only. |
| **`hishel`** | 1.4.0 · 2026-09-16 | HTTP | **RFC 9111** for httpx/httpcore and httpx2/httpcore2, sync and async, storages filesystem / Redis / SQLite / S3, transport-agnostic with drop-ins for httpx, httpx2 (`extra: httpx2`), requests and ASGI — **no `wreq` transport**, so with the house client RFC 9111 moves up a plane: `cashews` on the handler, or the proxy (→ `sys-gen-scaling`). Response caching is a solved protocol problem; do not reimplement it in a handler. **Caveat: 1.0 was a breaking rewrite** (`hishel._serializers` removed) — pin it and read the changelog. |

## Deliberately not primaries

| Library | Status 2026-09-17 | Why not |
|---|---|---|
| `diskcache` | 5.6.3 · **release 2023-08-31** | SQLite-backed, transactional, no daemon, 26.9M downloads/month — and three years without a release (maintainer at OpenAI). Reached **through `cashews`' disk backend**, which is where it still earns its place; named directly only for a sync CLI or script that wants persistence with no server. Its substrate is SQLite, so the stability is structural rather than maintained — but re-verify before a fresh adoption. |
| `moka-py` | 0.5.0 · 2026-08-21 | Binding to moka-rs (the Caffeine port) with TinyLFU, TTL+TTI and `wait_concurrent`. Genuinely good, and it loses to `cachebox` on maturity: pre-1.0 against a v6, and `cachebox` covers the same ground including the stampede lock. |
| `theine` | 2.0.0 · 2025-08-17 | The other Rust option: adaptive W-TinyLFU, timer wheel, Django adapter, stable 2.x API, and **free-threading 3.13.6+ support**. Switch to it if free-threading is the constraint; otherwise it is 13 months without a release. |
| `cachetools` | 7.2.0 · 2026-09-16 | Healthy and ubiquitous, but pure-Python: `cachebox` gives the same policies with a Rust core. The zero-build-dependency fallback, nothing more. |
| `asyncstdlib` | 3.14.0 · 2026-03-20 | Its `lru_cache`/`cached_property` are async-safe and correct, but it is an **async iteration toolkit** first and is owned by → `para-py-iteration`. Inside a lazy pipeline, use theirs; for a standalone async memo, `async-lru` is the dedicated tool. |
| `aiocache` | 0.12.3 · **2024-09-25** | The obvious async pick, and dead in the water: two years without a release, 67 open issues, still 0.x. 7.0M downloads/month is inertia, not health (rule 4: downloads are not maintenance). `cashews` supersedes it on every axis. |
| `dogpile.cache` | 1.5.0 · 2025-10-11 | The most pluggable of all (entry-point backend registry, memcached/redis/dbm/custom, SQLAlchemy org) and the original answer to the dogpile problem — but **sync-only**, which loses to the house async-first rule. |
| `cacheme` · `cacheout` | 2023-03-06 / 2023-12-22 | Unmaintained. |
| `fastapi-cache2` and friends | — | Framework-coupled by construction. A cache tied to one web framework cannot serve a worker, a CLI or a pipeline. |

## Servers, not libraries

The shared plane needs a server: **Valkey** (BSD-3, Linux Foundation, the open Redis fork; default on Ubuntu 24.04+/Debian 13) over Redis, now SSPL/RSAL/AGPL. Selection and topology → `sys-gen-scaling`; managed equivalents (ElastiCache, Memorystore, Azure Cache) → `ops-gen-cloud`. Client-side caching with server-driven invalidation is a protocol feature worth reaching for before building an L1/L2 by hand.
