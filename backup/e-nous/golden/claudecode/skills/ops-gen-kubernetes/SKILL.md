---
name: ops-gen-kubernetes
description: "Gen: Kubernetes object model — Pods, Deployments/StatefulSets, Services/Gateway API, ConfigMaps/Secrets, probes, HPA, Helm, GitOps. Use when deploying, exposing or scaling on Kubernetes."
metadata:
  family: delivery
---

# ops-gen-kubernetes

Kubernetes runs containers at scale by reconciling declared desired state. This skill maps its object model and the operations that matter, local-first (k3s on your own hardware) and portable to any cluster. It executes decisions made in `sys-gen-scaling`; the image it runs is `ops-gen-containers`; managed clusters → `ops-gen-cloud`. The tooling → `references/lib.md`.

## Rules

1. **Declare desired state; let the control loop reconcile.** Manifests in git, applied declaratively — never imperative `kubectl edit` as the source of truth. GitOps (Argo CD/Flux) reconciles from the repo. → `references/lib.md`
2. **Never a bare Pod.** A workload controller owns Pods: `Deployment` (stateless), `StatefulSet` (stable identity/storage), `Job`/`CronJob` (batch), `DaemonSet` (per-node). Controllers give self-healing and rollouts. → `references/workloads.md`
3. **Requests/limits and probes are mandatory.** Requests schedule the Pod, limits cap it, `readiness`/`liveness`/`startup` probes gate traffic and restarts. Missing them breaks scheduling and rollouts. → `references/scaling.md`
4. **Expose via Service + Gateway API.** A `Service` gives stable in-cluster addressing and L4 balancing; external L7 routing is the **Gateway API** (GA) — `Ingress` is feature-frozen legacy, prefer Gateway for new clusters. → `references/networking.md`
5. **Config in ConfigMap, secrets in Secret — and a real manager.** Externalize config; Secrets are base64, not encrypted — back them with sealed-secrets or an external manager. Isolate workloads with `Namespace` + RBAC. → `references/config.md`
6. **Autoscale on the trigger, not by default.** HPA on CPU, latency or queue depth is the *execution* of a `sys-gen-scaling` trigger — size requests right or the signal lies. → `references/scaling.md` · `sys-gen-scaling`
7. **Package per environment.** Helm or Kustomize templates the manifests across envs; keep the image identical, vary only config. → `references/lib.md`

## Sample

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: api, namespace: prod }
spec:
  replicas: 3                                  # stateless → horizontally scalable
  selector: { matchLabels: { app: api } }
  template:
    metadata: { labels: { app: api } }
    spec:
      containers:
        - name: api
          image: ghcr.io/eager/api@sha256:...  # pinned by digest
          resources:
            requests: { cpu: "250m", memory: "256Mi" }   # schedules
            limits:   { cpu: "1",    memory: "512Mi" }   # caps
          readinessProbe: { httpGet: { path: /health, port: 8012 } }
```

Three interchangeable replicas, resource-bounded, taken out of rotation until the readiness probe passes.

## References

- `references/workloads.md` — Pod, Deployment, StatefulSet, DaemonSet, Job/CronJob; rollouts
- `references/networking.md` — Service types, Gateway API vs Ingress, load balancing, NetworkPolicy
- `references/config.md` — Namespace, ConfigMap, Secret, RBAC, ServiceAccount
- `references/scaling.md` — requests/limits, probes, HPA/VPA, node pools, PodDisruptionBudget
- `references/lib.md` — the stack: kubectl, Helm/Kustomize, k9s, k3s (local), Argo CD/Flux
