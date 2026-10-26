# lib — the cloud stack

What to reach for across providers. Reach order: **self-hosted on the open interface → managed service on the same interface → provider-specific only when it wins decisively**. Select by capability (below); the per-provider service names live in `aws.md`/`gcp.md`/`azure.md`. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The cloud capability set × the nine software categories — what each typically provisions.

| Category | Cloud capability set |
|---|---|
| **API service** | managed K8s + L7 LB + managed Postgres + secret manager + CDN |
| **Async worker** | managed K8s + managed queue (Kafka-API/NATS) + object storage |
| **ML pipeline** | GPU node pool + object storage + registry + vector store |
| **Agent system** | managed K8s + Valkey + queue + secret manager |
| **Voice runtime** | low-latency compute + edge/CDN + regional pinning |
| **CLI tool** | none — or object storage for artifacts |
| **System script** | none — runs on a host |
| **Evaluation harness** | ephemeral compute + object storage for runs |
| **Library** | registry (`pkg`) — no infra |

## Capability catalog (the portable interface)

| Capability | Speak this interface | Self-hosted default |
|---|---|---|
| Orchestration | Kubernetes API | k3s |
| Object storage | S3 API | MinIO |
| Relational | Postgres wire | PostgreSQL |
| Cache | Redis protocol | Valkey |
| Queue/stream | NATS / Kafka API | NATS / Redpanda |
| Registry | OCI | any OCI registry |

## Tooling

| Tool | Role | License |
|---|---|---|
| `aws` / `gcloud` / `az` CLI | provider API access, scripting | vendor, free |
| provider Terraform/OpenTofu providers | provisioning (→ `ops-gen-iac`) | MPL/vendor |
| External Secrets Operator | surface cloud secrets into K8s | Apache-2.0 |

**Never:** design against a proprietary service name · long-lived static access keys (use OIDC/workload identity) · cross-region/egress-heavy topologies without counting the bill · a managed service where self-hosted on the same interface suffices · provisioning by console instead of `ops-gen-iac`.

## Testing

Validate IaC plans (→ `ops-gen-iac`); use provider emulators where they exist (LocalStack for AWS, `gcloud` emulators, MinIO for S3) to test integration without a live account or spend. Mark live-account tests slow and opt-in.
