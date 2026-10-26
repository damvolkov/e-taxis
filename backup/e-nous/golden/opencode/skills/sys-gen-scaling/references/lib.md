# lib — the distributed stack

The mechanisms behind the scaling patterns. This skill teaches the *design*; here are the go-to systems that run it. Local-first / self-hosted default (Damien runs his own hardware); the managed equivalents live in `ops-gen-cloud`. Open-source licensing matters for the `e-` prefix — prefer the LF-governed fork where a project was relicensed. Verify against `flow-gen-research` before pinning. Dates: 2026-09 (`awa`: 2026-10, 0.6.9).

## By software category

The distributed stack × the nine software categories.

| Category | Distributed stack |
|---|---|
| **API service** | `Valkey` (session/cache) · `Traefik`/`Envoy` (LB/gateway) |
| **Async worker** | `awa` (jobs on the Postgres you run) · `NATS` JetStream / `Redpanda` (streams) · autoscale on queue depth |
| **ML pipeline** | object storage for artifacts · `Redpanda` for event streams · `Valkey` feature cache |
| **Agent system** | `Valkey` shared memory/state · `NATS` for inter-agent messaging |
| **Voice runtime** | `NATS` low-latency pub/sub · `Valkey` for session routing |
| **CLI tool** | usually none — talks to the services above |
| **System script** | none — orchestration glue |
| **Evaluation harness** | `Valkey` result cache · object storage for runs |
| **Library** | none — stays transport-agnostic |

## Primary systems

| System | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `Valkey` | in-memory cache, coordination, shared state | any shared state behind stateless replicas | BSD-3, Linux Foundation — the open Redis fork; default on Ubuntu 24.04+/Debian 13. Redis is now SSPL/RSAL/AGPL |
| `awa` (`awa-pg`) | durable job queue in Postgres, Rust engine with Python workers (PyO3), async and sync clients; transactional enqueue, retries/backoff, cron, rate limits, DLQ, crash-safe leases | background jobs when Postgres already runs — no broker to operate; a job commits with the rows that caused it | MIT/Apache-2.0, hardbyte — young (first release 2026-03, 0.6.x) |
| `NATS` (JetStream) | lightweight broker, pub/sub, durable streams | decouple work; low-overhead messaging, self-hosted | Apache-2.0, CNCF — the pragmatic self-host pick |
| `Redpanda` | Kafka-API streaming, C++ (no JVM/ZooKeeper) | Kafka compatibility or high-throughput streams | BSL (source-available) — Kafka itself is Apache-2.0 |
| `Traefik` / `Envoy` | L7 load balancer, reverse proxy, gateway | route/balance across replicas, TLS termination | MIT / Apache-2.0 |

Python clients (`redis`/`valkey`, `nats-py`, broker SDKs) are the `data-py-cache`/`conc` concern, not this list. Managed equivalents (ElastiCache, SQS/PubSub, ALB…) → `ops-gen-cloud`.

**Never:** local state on a replica · sticky sessions instead of a shared store · unbounded producer without backpressure · a broker where a direct call suffices · a broker for job-shaped work when Postgres already runs (→ `awa`) · adopting a relicensed server when an LF-governed fork exists.

## Testing

`pytest` + `fakeredis`/an ephemeral broker container; assert idempotency (a redelivered message applies once), retry/backoff behavior, and graceful drain. Load/throughput claims → a measured benchmark, never asserted.
