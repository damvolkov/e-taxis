---
name: data-py-cache
description: "Python: what to cache and where — pure core, plane (process, disk, shared, HTTP client), keys, TTL, invalidation, stampede. Use when a repeated call is slow or costly. Not build, proxy or CDN caches."
metadata:
  family: stack
---

# data-py-cache

A cache is a bet that the same answer will be asked for again. Owns the whole bet: whether it pays, **which plane holds the value**, how the key is derived, when it dies, and what happens on the miss. Not here: whether load justifies caching at all (`sys-gen-scaling`), memoizing a DP recurrence as an algorithm (`algo-py-core`), async-safe cache decorators over iterables (`para-py-iteration`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Fix the algorithm before caching it.** A cache over an O(n²) loop buys latency with memory and hides the defect; the hit ratio flatters it until the key space grows. Name the complexity first → `algo-gen-selector`. Cache only what is already as cheap as it can be.
2. **Extract the pure core, then memoize that.** A recursion or a loop body that recomputes the same value is a decomposition problem, not a caching one: split the deterministic part into a pure function of hashable arguments, keep I/O, clock and randomness outside it, and cache the core. Caching the impure wrapper caches its side effects too. → `references/memoization.md`
3. **Pick the cheapest plane that answers the symptom, then the library that owns it.** In-process (ns, per-replica, dies with the process) → disk (µs, survives restart, one host) → shared store (ms, coherent across replicas) → HTTP/edge (zero origin traffic); climb only when the plane below cannot hold the invariant. Inside a plane the reach is builtin `functools` → Rust-backed → specialized: never name a library from memory, read the dated matrix. → `references/planes.md` · `references/lib.md`
4. **The key is a contract.** Derive it from every input that changes the value and nothing else; prefix a namespace and a schema version so a deploy invalidates without a purge. An unbounded or unhashable key space is a leak, not a cache. → `references/keys.md`
5. **Bound every cache: `maxsize` plus a policy.** Eviction is a memory decision (LRU/LFU/TTL/TinyLFU), invalidation is a correctness one — never let one stand in for the other. `@cache` on a method pins `self` and the instance never dies — a value that belongs to the instance is `cached_property`, not a cache. → `references/eviction.md`
6. **Declare the staleness you accept.** TTL, explicit purge on write, or event/tag invalidation — pick one and write down the window as a number. "Fresh enough" without a bound is a bug waiting for a demo. → `references/invalidation.md`
7. **Defend the miss.** Single-flight so N concurrent misses compute once, jitter so TTLs don't expire in step, negative caching so failures don't become a hot loop, and fail-open so a dead cache degrades latency, never availability. → `references/failure.md`

## Sample

```python
# ✗ the recursion re-solves the same subproblem AND re-reads the file every call
async def score(path: Path, depth: int) -> float:
    weights = json.loads((await anyio.Path(path).read_text()))      # I/O inside the recursion
    return weights[str(depth)] + (await score(path, depth - 1) if depth else 0.0)

# ✓ pure core extracted and memoized; I/O hoisted to the impure edge, cached on its own plane
@cachebox.cached(cachebox.LRUCache(maxsize=4096))                    # builtin @cache if the key
def _score(weights: tuple[float, ...], depth: int) -> float:         # space is provably small
    return weights[depth] + (_score(weights, depth - 1) if depth else 0.0)

async def score(path: Path, depth: int) -> float:
    return _score(await load_weights(path), depth)                   # load_weights: its own TTL
```

Two values, two lifetimes: the computation is pure and lives for the process, the file is I/O and expires on its own clock. Fusing them would cache the read forever or recompute the maths on every reload.

## References

- `references/memoization.md` — extracting the pure core from recursion and loops, key functions, hashability, methods vs functions, the async coroutine trap
- `references/planes.md` — the ladder process → disk → shared → HTTP/edge: what each plane costs, holds and loses
- `references/keys.md` — key derivation, namespace and schema version, cardinality, per-user partitioning
- `references/eviction.md` — sizing, LRU/LFU/TTL/TinyLFU, memory accounting, why eviction is not invalidation
- `references/invalidation.md` — TTL vs explicit vs event/tag, cache-aside and the write patterns, read-your-writes, staleness as an SLO
- `references/failure.md` — stampede and single-flight, jitter, negative caching, fail-open, cold start, poisoning
- `references/lib.md` — **which library**: cache plane × software category, the builtin floor, the four primaries, async/sync, every datum dated
