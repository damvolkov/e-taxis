---
name: ops-gen-cloud
description: "Gen: cloud across AWS/GCP/Azure and self-hosted — capability-first selection, managed vs self-run, portability, IAM, cost, secrets. Use when choosing or provisioning cloud or self-hosted services."
metadata:
  family: delivery
---

# ops-gen-cloud

Cloud is a mapping layer: the same capability — managed Kubernetes, object storage, a queue — has a different name per provider, and a self-hosted equivalent. This skill selects by *capability*, keeps the design portable, and maps it to AWS/GCP/Azure or your own hardware. It provisions via `ops-gen-iac`, runs workloads via `ops-gen-kubernetes`, and answers a need raised in `sys-gen-scaling`. Provider maps → `references/`.

## Rules

1. **Design agnostic, then map.** Choose the capability (managed K8s, object store, secret manager), never the brand; the provider references translate it. A design pinned to a service name is a design pinned to a vendor. → `references/aws.md` · `references/gcp.md` · `references/azure.md`
2. **Self-hosted is the baseline; cloud is the reach.** Damien runs his own hardware — k3s + MinIO + Postgres + NATS covers most needs. Reach for a managed cloud service when scale, reach or availability demands it, not by default. → `references/selfhosted.md`
3. **Portability is a design constraint.** Prefer open interfaces — Kubernetes, the S3 API, the Postgres wire protocol — over proprietary services; an escape hatch keeps negotiating leverage and avoids lock-in.
4. **Managed vs self-run is a plane decision.** A managed DB/queue/cluster trades money for removed ops toil; self-host when control, cost or data residency wins. Decide by the cheapest plane (AGENTS.md rule #19).
5. **IAM least privilege.** Cloud identity is the security boundary: per-workload roles, no wildcard grants, no long-lived static keys — workload identity / OIDC federation instead.
6. **Cost is an architecture signal.** Egress, idle managed services and oversized instances dominate the bill; right-size, scale-to-zero, keep data in one region. The invoice reflects the design.
7. **Secrets in the provider's manager, injected at runtime.** Never in images or repos; the cloud secret store + workload identity, surfaced to the pod via External Secrets. → `ops-gen-kubernetes`

## Sample

```markdown
Capability-first selection (fill the row, then read the provider map):
| Capability        | Agnostic choice     | Self-hosted   | AWS      | GCP            | Azure          |
|-------------------|---------------------|---------------|----------|----------------|----------------|
| Managed Kubernetes| K8s API             | k3s           | EKS      | GKE            | AKS            |
| Object storage    | S3 API              | MinIO         | S3       | Cloud Storage  | Blob Storage   |
| Queue / broker    | NATS / Kafka API    | NATS/Redpanda | SQS      | Pub/Sub        | Service Bus    |
```

Decide the capability and the interface first; the provider column is a lookup, not a design choice.

## References

- `references/selfhosted.md` — the own-hardware baseline: k3s, MinIO, Postgres, NATS, Traefik
- `references/aws.md` — capability → AWS service map, with the lock-in and cost notes
- `references/gcp.md` — capability → GCP service map
- `references/azure.md` — capability → Azure service map
- `references/lib.md` — the stack: CLIs/SDKs, the capability catalog, portability escape hatches
