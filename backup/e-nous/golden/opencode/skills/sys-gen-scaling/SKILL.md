---
name: sys-gen-scaling
description: "Gen: distributed design, horizontal scaling — triggers, vertical before horizontal, stateless services, queues, caching, resilience. Use when load, replicas or a backlog raise a scaling question."
metadata:
  family: design
---

# sys-gen-scaling

The entry to the infrastructure plane: decide *whether*, *why* and *how* to scale — before writing any YAML. Owns the scaling decision, agnostic to the tool. The first job is to tell a real scaling trigger from premature complexity (rule #19: solve each concern at its cheapest layer). Execution — Docker, Kubernetes, IaC, cloud — lives in `ops-*`; workers in `conc-py-async`; cache mechanics in `data-py-cache`. The distributed stack → `references/lib.md`.

## Rules

1. **Classify the plane before designing.** Is this a scaling problem at all, or over-engineering the backend? Name the trigger (rule below) or stop. Vertical and in-process first → `conc-py-async`.
2. **Vertical before horizontal.** Exhaust one node — all cores, right data structures — before adding nodes; horizontal buys throughput at the price of coordination, network and failure modes.
3. **Name the scaling trigger.** RPS/concurrency, latency SLO, task backlog, node ceiling, availability, elasticity, data volume, or geography — each maps to a specific response, not to "more code". → `references/triggers.md`
4. **Stateless is the enabler.** A horizontally-scaled service holds no local state — session and data live in a shared store; sticky sessions and on-disk state block replication. → `references/patterns.md`
5. **Decouple work with a queue.** Background and fan-out work goes through a broker; workers scale on queue depth, not on request threads. Topology here, the worker itself → `conc-py-async`. → `references/patterns.md`
6. **Cache to shed load, not to hide a flaw.** Cache the expensive, idempotent read; invalidation and staleness are the real cost. Mechanism → `data-py-cache`.
7. **Design for failure.** Replicas die: health checks, retries with backoff + jitter, idempotency, backpressure and circuit breakers are not optional at N nodes. → `references/resilience.md`

## Sample

```markdown
Scaling decision card — emit before touching infrastructure:
- Symptom: p99 latency breaches SLO at 800 RPS; one instance pins 1 core
- Trigger: request concurrency (#1) + latency SLO (#2)
- Vertical checked?: yes — loop CPU-bound, already offloaded, one node saturated
- Response: stateless replicas behind a load balancer, autoscale on CPU/latency
- Plane: infrastructure (→ ops-gen-kubernetes HPA), not application code
- Rejected: adding an in-process worker pool — would contend, not scale
```

The card forces the question "is this the cheapest plane?" before any YAML or backend change.

## References

- `references/triggers.md` — the eight scaling triggers: signal, response, and what NOT to build
- `references/patterns.md` — stateless services, queue topology, partitioning/sharding, replication, load balancing
- `references/resilience.md` — retries/backoff/jitter, idempotency, circuit breakers, backpressure, health checks, graceful shutdown
- `references/lib.md` — the distributed stack: cache/coordination, broker, load balancer/proxy
