# planes — where the value lives

Four planes, four different bets. Climbing costs latency and coordination; staying low costs coherence. Pick the lowest plane that can hold the invariant you need, and know what you lose by being there.

| Plane | Latency | Survives | Shared by | Costs |
|---|---|---|---|---|
| In-process | ~100 ns | nothing | one process | RAM per replica, cold on every restart, incoherent across replicas |
| Disk | ~10–100 µs | restart | one host | serialization, fsync, disk pressure, still per-host |
| Shared store | ~0.3–2 ms | restart, deploy | every replica | a network hop, a dependency that can fail, serialization |
| HTTP / edge | 0 origin work | per its own TTL | every client | only for HTTP semantics, correctness governed by RFC 9111 |

## In-process

The default. A dict with a policy in front of it: nanoseconds, no serialization, no network, the value stays a live Python object.

Reach for it when the value is **expensive to compute and cheap to hold**, and when every replica computing its own copy is acceptable. Model weights, compiled regexes, parsed config, a pure function's results.

What it loses:

- **Cold start.** Every deploy, restart and autoscale event starts empty. If your p99 depends on a warm cache, you have coupled latency to deploy frequency. Either warm it deliberately or accept the first-request penalty.
- **Incoherence at N replicas.** Ten replicas hold ten versions of the same key. Fine for immutable values, wrong for anything a write can change — an invalidation reaches the replica that handled the write and no other.
- **Memory is per replica.** A 500 MB cache × 10 pods is 5 GB, and the OOM killer does not care that it was "just a cache".

Under replicas this plane is an optimization you can cold-start, never a source of truth → `sys-gen-scaling`.

## Disk

Local persistence: survives restarts, outlives the process, stays on one host. In Python this is SQLite under the hood — transactional, no daemon, no port.

Reach for it when the value is **expensive to compute, too big for RAM, and host-local is fine**: model artifacts, downloaded datasets, scraped pages, embeddings for a batch job, anything a CLI wants to remember between runs.

What it loses: serialization on every get and set (pickle is fast and unsafe across trust boundaries; prefer an explicit format), disk pressure that nobody monitors until it is full, and the same per-host incoherence as in-process. In a container, remember the filesystem is ephemeral unless you mounted a volume — a disk cache on an overlay fs is an in-process cache with extra steps.

## Shared store

One value, every replica. This is where a cache stops being an optimization and starts being infrastructure: it has a network hop, an availability number and a failure mode.

Reach for it when replicas must agree, when the value is expensive enough to justify a round trip, or when you need invalidation to actually reach everyone. Sessions, rendered pages, API responses, rate-limit counters, anything a write must be able to purge.

What it costs:

- **A dependency.** The cache can be down while your service is up. Fail open: a miss on a dead cache is a slow request, not a 500.
- **Serialization.** The value crosses a socket, so it must be bytes. Large objects make the hop dominate the saving you were chasing.
- **A coherence protocol you now own.** Two replicas writing the same key is a race you have to think about.

Note the client-side caching (tracking/invalidation push) that modern Redis-protocol servers offer: a local copy per client that the server invalidates. It is the in-process plane with coherence bolted on, and it is the right answer more often than people reach for it.

## HTTP / edge

If the value is an HTTP response, the protocol already has a cache with twenty years of semantics: `Cache-Control`, `ETag`, `Last-Modified`, `Vary`, conditional requests, `stale-while-revalidate`. Implementing your own response cache in a handler reimplements RFC 9111, badly.

Two directions, both worth using:

- **Outbound** — your client caching upstream responses. A conditional request that gets a `304` costs a round trip and no body; a fresh hit costs nothing.
- **Inbound** — your responses cached by proxies, CDNs and browsers. This is the cheapest plane that exists: the request never reaches you. It is also a configuration concern, not application code (rule #19) → `sys-gen-scaling`, `ops-gen-kubernetes`.

`Vary` is where this goes wrong: forget it and a per-user response gets served to everyone. Any header that changes the body must be in `Vary`, or the response must be `private`.

## Layering

Real systems stack planes: a process-local L1 in front of a shared L2, with the L2 holding truth and the L1 absorbing the hot keys. It works, and it doubles your invalidation problem — purging L2 leaves N stale L1 copies until their own TTL burns out. Only layer when a measurement says the L2 hop is the bottleneck, and give L1 a TTL short enough that the staleness window is one you wrote down.
