# lib — the Kubernetes stack

What to reach for to run and operate a cluster. Reach order: **`kubectl` + Kustomize (builtin) → Helm (packaging) → Argo CD/Flux (GitOps)**; `k3s` for a local/self-hosted cluster on your own hardware. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The Kubernetes stack × the nine software categories. It changes little — what varies is the workload kind (Deployment vs StatefulSet vs Job) and whether the cluster is local or managed.

| Category | Kubernetes stack |
|---|---|
| **API service** | Deployment + Gateway API + HPA; Helm chart, Argo CD |
| **Async worker** | Deployment + HPA on queue depth; KEDA for event-driven autoscale |
| **ML pipeline** | Job/CronJob or Deployment on a GPU node pool; StatefulSet for a model store |
| **Agent system** | Deployment; Valkey/NATS as in-cluster services |
| **Voice runtime** | Deployment with low-latency networking; node affinity |
| **CLI tool** | runs as a Job, or off-cluster entirely |
| **System script** | CronJob for scheduled cluster tasks |
| **Evaluation harness** | Job for reproducible runs; parallelism/completions |
| **Library** | none — not deployed |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `kubectl` + Kustomize | cluster CLI + overlay-based manifest templating | always; env overlays without a templating language | Apache-2.0 (built in) |
| Helm | package manager, charts, releases | reusable/parametrized app packaging | Apache-2.0, CNCF |
| Argo CD / Flux | GitOps — reconcile cluster from git | declarative continuous delivery | Apache-2.0, CNCF |
| `k3s` | lightweight single-binary Kubernetes | local / self-hosted / edge cluster | Apache-2.0, CNCF |

Operate/observe with `k9s` (TUI); event-driven autoscale with `KEDA`; managed control planes (EKS/GKE/AKS) → `ops-gen-cloud`.

**Never:** imperative `kubectl edit` as the source of truth · bare Pods · missing requests/probes · `Ingress` for a new cluster (use Gateway API) · raw Secret manifests in git · one giant namespace for everything.

## Testing

Validate manifests (`kubeconform`), dry-run apply, and policy-check (`conftest`/OPA) in CI. Smoke-test rollouts on a `k3s`/`kind` ephemeral cluster: probe readiness, roll and rollback, assert the PDB holds.
