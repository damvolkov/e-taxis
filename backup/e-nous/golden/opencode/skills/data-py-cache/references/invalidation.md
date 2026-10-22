# invalidation — deciding how wrong you are willing to be

There are only two hard things in computer science, and this is one of them. The trap is that invalidation looks like an implementation detail and is actually a product decision: *how stale may this value be before someone is harmed?* Answer that in seconds, write it down, and the mechanism follows. Refuse to answer and you will pick a TTL by superstition.

## Staleness is an SLO

For every cached value, state the window:

```
product price      → 0 s     never cache the authoritative read; cache the render
search results     → 60 s    stale results are a nuisance, not a fault
user profile       → 300 s   with explicit purge on write
model vectors      → ∞       immutable per deploy; the version key handles it
permissions        → 0 s     a stale allow is a security bug
```

The window is what makes a mechanism choosable. `∞` means the value is immutable and the key carries its version. `0` means do not cache it at this plane — cache something derived from it instead.

## The three mechanisms

| Mechanism | Staleness | Cost | Use when |
|---|---|---|---|
| **TTL expiry** | up to the TTL, always | none | the window is acceptable and writes are not observable by the writer |
| **Explicit purge on write** | near zero for the writer | coupling: the write path must know every key it invalidates | a user must see their own write |
| **Event / tag invalidation** | near zero, fan-out | an index or a bus to maintain | many derived entries depend on one entity |

They stack. The honest default for most systems is **TTL as the floor, explicit purge as the fast path**: the purge handles the common case, the TTL is the backstop for every purge you forgot or that failed. A purge-only design has no backstop, and one missed call means a permanently wrong entry.

## Write patterns

Where the write goes decides what the cache can promise.

- **Cache-aside (lazy loading)** — read: miss → load → populate. Write: update the store, then **delete** the key. The default; simple, and the cache only ever holds what was actually asked for.
  *Delete, do not update.* Writing the new value into the cache on write reintroduces the race that deletion avoids: two concurrent writers can interleave and leave the older value resident.
- **Write-through** — write goes to cache and store together. The cache is always warm and consistent; every write pays the cache latency, and you cache things nobody reads.
- **Write-behind (write-back)** — write hits the cache, the store is updated asynchronously. Fast, and the cache is now a durability risk: a crash loses acknowledged writes. Only with a durable queue and a real reason.
- **Write-around** — write goes to the store only, bypassing the cache. Right for write-heavy data that is rarely read back; the first reader pays the miss.

## Read-your-writes

The user who just saved something and then sees the old value has caught you. Three fixes, cheapest first:

1. **Purge synchronously in the write path**, before the response returns. Covers the single-replica and shared-store cases.
2. **Serve the writer from the source** for a short window — a cookie or a header that bypasses the cache for N seconds after their write.
3. **Version the read** — the write returns a version the client sends back, and a cache entry older than it is treated as a miss.

At N replicas with a per-process cache, none of these work: the purge only reaches the replica that handled the write. That is the plane's limitation, not a bug to code around — move the value to the shared plane or shorten the local TTL to the staleness you promised.

## Tags, when a prefix is not enough

When one entity change invalidates entries scattered across namespaces, prefix deletion cannot find them. A tag index — entry → tags, tag → entries — makes "drop everything touching product 42" a single call. Maintaining it costs a write per tag per entry; some cache frameworks do it for you, and that is a good reason to pick one over rolling your own.

## Two things that are not invalidation

- **Eviction.** Dropping an entry for memory is not the same as dropping it for correctness; a cache that stays under its limit never evicts, and your stale data lives forever.
- **Flushing everything.** It "works" and it hands you a synchronized stampede: every replica missing on every hot key simultaneously. If you must, do it with jitter, or bump the version key and let the old entries die quietly instead.
