# keys — the contract between the value and its inputs

A cache key is a claim: *everything that can change this value is in here, and nothing else is*. Break the first half and you serve wrong data. Break the second and your hit rate collapses while memory grows. Every cache bug that is not an invalidation bug is a key bug.

## Derivation

Include every input the value depends on:

- the arguments that change the result — and only those;
- the identity it is scoped to (tenant, user, locale) when the value is not global;
- the **schema version** of the stored shape;
- the **namespace** of the producing code.

Exclude everything else: request ids, timestamps, trace headers, a `verbose` flag that changes logging but not the value. Each one multiplies the key space and drops the hit rate toward zero.

```python
_NS = "rank"          # producing code
_V = 3                # bump on any change to the stored shape OR the algorithm

def _key(tenant: str, query: str, top_k: int) -> str:
    return f"{_NS}:v{_V}:{tenant}:{top_k}:{sha256(query.encode()).hexdigest()[:16]}"
```

## The version prefix is your deploy-time invalidation

This is the highest-value trick in this file. When the algorithm changes or the stored shape changes, **bump the version and every old key becomes unreachable at once** — no purge, no scan, no migration, no downtime. Old entries age out under their own TTL while the new ones fill in.

Without it, a deploy that changes the meaning of a value leaves the previous meaning in the cache, and you are serving last release's answers with this release's code. The version belongs in the key, not in the value: a value you must deserialize before you can tell it is stale has already cost you the read.

## Cardinality

Key space size decides whether you have a cache or a leak.

| Key derived from | Cardinality | Verdict |
|---|---|---|
| Enum, depth, small int range | bounded, tiny | memoize freely, unbounded is fine |
| Entity id | bounded by the entity count | fine with `maxsize` |
| Normalized search query | long tail | fine, expect a modest hit rate |
| Raw user text | effectively unbounded | hash it, bound it, expect near-zero hits |
| Timestamp, uuid, request id | unique per call | **never a key** — 0% hits, 100% cost |

If the key is unbounded, the question is not "which eviction policy" but "is there a hit at all". Measure the repeat rate before building anything.

## Normalize before you key

Two requests that mean the same thing should produce the same key. Normalize at the boundary: case-fold, strip, sort query parameters, canonicalize the locale, round floats to the precision that actually matters. `"  Madrid "` and `"madrid"` are one key or two, and that decision is worth more than the eviction policy.

The inverse error is over-normalization: folding away a distinction that *does* change the value, which serves one tenant's data to another.

## Long keys and digests

Shared stores hold the key in memory too. A 2 KB key with a 200-byte value inverts the economics. Hash anything long — the digest is fixed-width and comparable — but keep the human-readable prefix so you can still find things:

```
rank:v3:acme:10:9f2c1a7b3e5d4f60          # namespace, version, tenant, params, digest
```

Truncating a SHA-256 to 16 hex chars is 64 bits: collision-safe for any realistic key population, and it keeps the key scannable by eye.

## Partitioning by identity

Any value that differs per user, tenant or locale must carry that identity in the key. Getting this wrong is the worst bug in this document — it leaks one principal's data to another, and the cache makes it intermittent and therefore hard to reproduce.

Two guards:

- Put the identity **first** after the namespace, so a prefix scan can purge one tenant.
- If a value *can* be per-user, make the key function take the identity as a required argument. A default of `None` is how "global by accident" happens.

The HTTP form of this is `Vary` — any header that changes the body must be declared, or a shared proxy will serve one user's response to the next.

## Invalidation-friendly shapes

Design the key so you can find the entries you will later need to drop:

- **Prefix scans** — `{ns}:v{n}:{tenant}:…` lets you purge a tenant. Cheap in a store with pattern deletion, expensive in one without.
- **Tags** — when the entries to drop do not share a prefix (everything touching product 42, across three namespaces), a tag index is the only sane answer; some cache frameworks maintain it for you.
- **Never plan on a full flush.** Flushing is a stampede with extra steps: every replica misses at once on the same keys.
