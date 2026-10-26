# eviction — bounding memory, not correctness

Eviction answers "I am full, what do I drop?". Invalidation answers "this entry is now wrong". They are different questions with different failure modes, and conflating them is how caches end up either leaking or serving stale data. **Eviction is never a correctness mechanism**: a TTL that happens to keep data fresh enough is a coincidence you are relying on.

## Bound everything

An unbounded cache is a memory leak with a hit-rate metric. The only safe exception is a key space that is provably small and fixed — an enum, a recursion depth, a config lookup. Everything keyed on anything a user can influence gets a `maxsize`.

Two ways to bound, and you usually want both:

- **By entries** (`maxsize=N`) — simple, predictable, and wrong when entry sizes vary by three orders of magnitude.
- **By weight** — N bytes total, each entry costing its real size. Correct when values are heterogeneous; requires a weigher and costs a little per insert.

Sizing is measurement, not intuition: take the working set, multiply by the entry size, compare against the memory you are willing to spend per replica, and remember it is per replica.

## Policies

| Policy | Keeps | Good for | Fails on |
|---|---|---|---|
| **LRU** | recently used | temporal locality, sessions | a scan — one sweep of cold keys flushes the hot set |
| **LFU** | frequently used | stable popularity distributions | shifting popularity; old hits keep dead keys alive |
| **TTL** | whatever has not expired | values with a known freshness window | says nothing about memory — pair it with a size bound |
| **TinyLFU / W-TinyLFU** | admission-filtered, frequency-aware | general purpose; the current default answer | almost nothing — it is LRU's replacement, not a niche |
| **FIFO** | the newest | nothing you want | ignores usage entirely |

**TinyLFU** is the one to know. It puts an *admission filter* in front of the cache: a new key only evicts an incumbent if a compact frequency sketch says it is likely to be used more. That single change makes the cache scan-resistant — a bulk read of cold keys no longer destroys the hot set, which is LRU's defining failure. Adaptive variants tune the window between recency and frequency at runtime. When a library offers it, take it; the hit-ratio gap over LRU on real workloads is large and free.

## TTL vs TTI

- **TTL** (time to live) — dies N seconds after it was *written*. Bounds staleness. This is the one you reason about.
- **TTI** (time to idle) — dies N seconds after it was last *read*. Bounds memory by dropping what nobody wants, while a hot key stays forever.

They compose: TTI to shed the cold tail, TTL to cap how stale the hot keys can get. A TTI alone means a popular key is never refreshed, which is a correctness hole wearing a memory-management costume.

## The hit ratio is the only number that matters

A cache justifies itself by arithmetic, not by existing:

```
saving = hit_ratio × (cost_miss − cost_hit) − (1 − hit_ratio) × cost_lookup
```

A 90% hit ratio on a 200 ms computation is transformative. A 10% hit ratio on a 2 ms one is a slower system with more moving parts. Measure the hit ratio before tuning the policy — policy choice moves it by percentage points, key design and plane choice move it by an order of magnitude.

Instrument three counters from day one: hits, misses, evictions. A rising eviction rate with a flat hit ratio means the cache is too small; a flat eviction rate with a low hit ratio means the key space is wrong. → `obs`

## Memory accounting in Python

- The cache holds **references**, so an entry pins the whole object graph it points at. A cached small dataclass holding a 200 MB dataframe costs 200 MB.
- The dead-instance trap: a cache keyed on `self` keeps every instance alive. → this skill's memoization reference.
- Weak-valued caches (`WeakValueDictionary`) let entries vanish when nobody else holds them — right for interning and identity maps, wrong for a real cache, because the values you most want to keep are exactly the ones nothing else references.
- Measure the real footprint (`sys.getsizeof` is shallow and will lie to you); size against the container limit you actually deploy with, not the laptop.
