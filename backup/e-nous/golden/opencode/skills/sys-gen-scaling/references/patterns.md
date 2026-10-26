# patterns — distributed design

The structural moves that make horizontal scale possible. Agnostic; the tooling that runs them is `ops-*`.

## Stateless services

A replica must be interchangeable: any instance can serve any request. That requires **no local state** —

- Session/auth state → a shared store (Valkey) or a stateless token (JWT).
- Uploaded/working files → object storage, not the pod's disk.
- In-memory caches → acceptable only as a per-instance optimization that can be cold-started, never as a source of truth.

Sticky sessions are a smell: they pin a user to an instance and defeat load balancing and failover. Externalize the state instead.

## Queue decoupling

Synchronous request → response couples the caller to the slowest step. Move slow, bursty or fan-out work behind a broker:

```
API (accept, enqueue, 202) → broker → workers (scale on queue depth) → result store / callback
```

- The API stays fast and stateless; workers absorb the load.
- Autoscale workers on **queue depth / lag**, not on request threads.
- The worker implementation and concurrency → `conc-py-async`.

## Partitioning / sharding

When data won't fit or perform on one node, split it:

- **Hash partitioning** — even spread, no range queries.
- **Range partitioning** — range/scan friendly, risks hot partitions.
- Route by a stable **partition key**; rebalancing is the hard part — pick a key with even distribution and low churn.

## Replication

Copies for read-scale and availability:

- **Read replicas** absorb read load; beware replication lag (read-your-writes).
- **Leader/follower** for failover; promotion must be automatic and idempotent.
- Replication trades consistency for availability — decide where you sit (the CAP/PACELC trade).

## Load balancing

Spread requests across replicas:

- **L4** (TCP) vs **L7** (HTTP-aware: path/host routing, retries, headers).
- Strategies: round-robin, least-connections, consistent-hashing (cache affinity without stickiness).
- Health checks remove dead replicas from rotation; drain on shutdown (→ `resilience.md`).
- In Kubernetes this is a Service + Gateway/Ingress → `ops-gen-kubernetes`.
