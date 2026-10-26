# scaling — resources, probes, autoscaling

The cluster-side execution of `sys-gen-scaling` triggers. Get resources and probes right first, or autoscaling reacts to a lie.

## Requests & limits

- **Requests** = what the scheduler reserves; too low → the node oversubscribes and thrashes, too high → wasted capacity.
- **Limits** = the hard cap; exceeding memory → OOM-kill, exceeding CPU → throttling.
- Set both per container; right-sizing comes from real measurement (→ profiling in `algo-py-core`), not guesses.
- Quality of Service: `requests == limits` → Guaranteed (evicted last); requests-only → Burstable; none → BestEffort (evicted first).

## Probes

| Probe | Question | On failure |
|---|---|---|
| `startupProbe` | has it finished booting? | hold the other probes until it passes |
| `readinessProbe` | can it serve now? | remove from Service endpoints (no traffic) |
| `livenessProbe` | is it wedged? | restart the container |

A missing readiness probe sends traffic to a cold Pod; an over-eager liveness probe restart-loops a slow-but-healthy app. Tune thresholds to real startup/latency.

## Horizontal Pod Autoscaler (HPA)

- Scales replica count on a metric: CPU/memory, or custom/external (latency, **queue depth** for workers — trigger #3 in `sys-gen-scaling`).
- Needs accurate requests (CPU % is relative to request). Set `minReplicas`/`maxReplicas` and stabilization windows to avoid flapping.
- **VPA** right-sizes requests/limits instead of count — don't run VPA and HPA on the same CPU metric.

## Disruption & nodes

- **PodDisruptionBudget** keeps a minimum available through voluntary disruptions (drains, upgrades) — pairs with rolling updates for lossless rollouts.
- **Node pools / autoscaler** add nodes when Pods can't be scheduled; taints/tolerations and affinity place workloads (GPU pool for ML → `ops-gen-cloud`).
- Cluster autoscaling is the node-level answer to trigger #4 (node ceiling); it complements, not replaces, the HPA.
