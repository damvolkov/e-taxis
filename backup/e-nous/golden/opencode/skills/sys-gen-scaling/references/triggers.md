# triggers — what pushes toward horizontal scale

The first and most valuable step: identify which trigger you actually have. Each has a measurable signal and a specific response. **None is fixed by making the Python backend cleverer** — that is the whole point of the plane distinction (AGENTS.md rule #19). If none applies, you are over-engineering; stop.

| # | Trigger | Signal (measure it) | Response | Don't build |
|---|---|---|---|---|
| 1 | Request concurrency | RPS / concurrent connections exceed one instance's throughput | stateless replicas + load balancer | an in-process mega-pool |
| 2 | Latency SLO under load | p95/p99 degrades as one node's CPU/loop saturates | autoscale on CPU/latency | micro-optimizations that don't touch the bottleneck |
| 3 | Task backlog | broker queue depth grows faster than a worker drains it (geometric fan-out) | horizontal workers on a shared queue, autoscale on depth | more threads inside one worker |
| 4 | Node resource ceiling | CPU/RAM of the machine exhausted, vertical spent | spread across nodes | a bigger single machine past the price/perf knee |
| 5 | Availability / redundancy | a single instance is a SPOF | N replicas across zones, health checks, failover | app-level HA logic the platform provides |
| 6 | Elasticity / spikes | bursty load (campaigns, nightly batch) | elastic autoscaling, scale-to-zero | permanent capacity for a transient peak |
| 7 | Data volume with state | an index/dataset won't fit or perform on one node | partitioning/sharding, read replicas | cramming it into app memory |
| 8 | Geographic distribution | latency by locality, data residency | multi-region, edge/CDN | a single region with clever caching only |

## Reading the signal

- **Wall-clock ≫ CPU-time** on a request path → IO-bound waiting; scaling replicas helps only if the downstream can take it (else fix the downstream, triggers 4/7).
- **One core pinned, queue empty** → CPU-bound; vertical/offload first (`conc-py-async`), then replicas.
- **Queue depth rising monotonically** → trigger 3; add consumers, or the producer is unbounded (backpressure, → `resilience.md`).
- **Errors/timeouts under load, not slowness** → capacity or resilience problem, not throughput (triggers 4/5).

## The over-engineering test

Before designing anything: *would one more replica, or the platform's own autoscaler, resolve this?* If yes, that is the plane — not the backend. Heavy in-process resource management on a service that already scales out on small nodes adds contention, not throughput.
