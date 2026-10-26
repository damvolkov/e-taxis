# failure — what the cache does when it does not help

A cache is judged on its hits and killed by its misses. Every failure mode here is a miss that arrives at the worst possible moment: all at once, on the hottest key, or while the backend is already struggling.

## Stampede (dogpile, thundering herd)

A popular key expires. Every concurrent request misses, every one of them starts the expensive computation, and the backend takes N times the load it was built for — at exactly the moment the cache was supposed to be protecting it. The cache did not fail; it amplified.

**Single-flight** is the fix: the first miss computes, everyone else waits on that result.

```python
async def get_or_compute(key: str) -> Value:
    if (hit := await cache.get(key)) is not None:
        return hit
    async with locks[key]:                       # one computation per key, process-wide
        if (hit := await cache.get(key)) is not None:   # re-check: someone may have filled it
            return hit
        value = await expensive(key)
        await cache.set(key, value, ttl=300)
        return value
```

The double-check after acquiring the lock is not optional — without it every waiter recomputes the moment it wakes.

At one process a lock is enough. Across replicas you need a distributed lock, and now you own lock expiry, the crashed-holder case and clock skew. Before building that, ask whether **early recomputation** solves it instead: refresh the value in the background at 80% of its TTL, so the entry is never actually absent and nobody ever waits. It costs one background refresh per key per TTL and removes the problem rather than coordinating it. Several cache libraries ship this as a decorator — take theirs.

## Synchronized expiry

A thousand keys written by the same deploy with the same TTL expire in the same second. Each is individually fine; together they are a stampede on the whole key space. **Jitter every TTL**: `ttl * random.uniform(0.9, 1.1)` is enough to smear the cliff into a slope. Do it by default, not after the incident.

## Cold start

A restart, a deploy or a scale-out event starts with an empty cache. If your p99 assumes a warm cache, your p99 is a lie you tell between deploys — and autoscaling makes it worse, because the new replica that was added to absorb load arrives with zero hits and is the slowest one in the pool.

- Warm deliberately at startup for a small, known hot set.
- Stagger rollouts so replicas do not all warm at once.
- Or accept it, measure it, and make sure the origin can survive a full cold start — which is the real test: **your system must be correct and survivable with the cache empty.** If it cannot serve at all without the cache, that is not a cache, it is an undeclared database.

## Negative caching

An expensive lookup that returns "not found" is expensive too. Without a negative entry, every request for a missing id pays full price, and a scan of nonexistent ids becomes a free denial of service.

Cache the absence — with a **much shorter TTL** than a hit, because a thing that does not exist now probably will soon, and serving "not found" for a resource the user just created is its own bug. Distinguish the sentinel from `None` so "cached absence" and "cache miss" are not the same value.

Do not negative-cache errors. A timeout is not an answer; caching it turns a transient blip into a sticky outage.

## Fail open

The shared cache will be unavailable at some point. Decide now what happens:

- **Fail open** (correct default) — a cache error is logged and treated as a miss. Slower, still serving.
- **Fail closed** — the request errors. Only when the cache is load-shedding infrastructure and the origin genuinely cannot take the traffic.

Wrap cache reads so an exception cannot escape into the request path, and put a timeout on them: a cache that takes 5 s to answer is worse than no cache, because you now pay both. If the cache stays down, a circuit breaker stops each request from re-paying the timeout — several cache frameworks include one.

## Poisoning

Whatever you write, you will read back and trust. Two rules:

- **Never cache a partial or failed result.** Write only on the success path. An exception mid-computation must leave the key absent, not half-populated.
- **Deserialization is a trust boundary.** Pickle executes on load; never point it at a store that anything untrusted can write to. Prefer an explicit, non-executing format for anything crossing a process — and validate the shape on read, because a schema change is indistinguishable from an attack at the deserializer. → `arch-py-adt`, `sec`

Cancellation is the quiet case: if the computing task is cancelled, its waiters must not inherit a half-built entry, and the lock must be released. → `lang-py-lifecycle`
