# workloads — the Pod controllers

The **Pod** is the smallest deployable unit: one or more co-located containers sharing network and storage. You almost never create one directly — a controller does, so it self-heals and rolls out.

| Controller | Use for | Gives |
|---|---|---|
| **Deployment** | stateless services (APIs, workers) | ReplicaSet management, rolling updates, rollback |
| **StatefulSet** | stateful apps (databases, brokers) | stable network id, ordered start/stop, per-Pod persistent volume |
| **DaemonSet** | one Pod per node (log/metric agents) | node-wide coverage |
| **Job** | run-to-completion batch | retries, completions/parallelism |
| **CronJob** | scheduled batch | Job on a cron schedule |

## Deployment & rollouts

- A Deployment owns a ReplicaSet owning Pods. Changing the template creates a new ReplicaSet and shifts Pods over.
- **Rolling update** (default): `maxSurge`/`maxUnavailable` bound how many Pods change at once; readiness probes gate each step. `kubectl rollout undo` reverts.
- Combine with a **PodDisruptionBudget** so voluntary disruptions (drains, upgrades) never drop below a minimum → `scaling.md`.

## StatefulSet

- Stable identity `pod-0, pod-1…` and a bound PVC per Pod — required when replicas are not interchangeable (leader election, sharded storage).
- Ordered, graceful scaling. More operationally expensive than a Deployment; use only when identity/storage demands it.

## Job / CronJob

- Job: `completions` and `parallelism` for batch fan-out; `backoffLimit` for retries; set `activeDeadlineSeconds`.
- CronJob: a schedule plus concurrency policy (`Forbid`/`Replace`/`Allow`) — for periodic work that isn't a long-running worker. Continuous queue consumers are a Deployment, not a CronJob → `sys-gen-scaling`.

## Pod design

- One primary process per container; sidecars (proxy, log shipper) share the Pod when they must share network/volume.
- `initContainers` run to completion before the app starts (migrations, waits).
- Graceful shutdown: the container handles `SIGTERM` within `terminationGracePeriodSeconds` → `ops-gen-containers`.
