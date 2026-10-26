# lib — the IaC stack

What to reach for to provision infrastructure. Reach order: **OpenTofu (open, HCL) → Pulumi (real languages) → a config-management tool only for the host layer**. Open licensing matters for the `e-` prefix. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The IaC stack × the nine software categories. It varies little — what changes is *what* is provisioned, not the tool.

| Category | IaC stack |
|---|---|
| **API service** | OpenTofu: cluster + network + DB + DNS/TLS |
| **Async worker** | OpenTofu: cluster + managed broker/queue |
| **ML pipeline** | OpenTofu: GPU node pool + object storage + registry |
| **Agent system** | OpenTofu: cluster + Valkey/broker + secret store |
| **Voice runtime** | OpenTofu: compute with low-latency networking |
| **CLI tool** | usually none — no infra to provision |
| **System script** | none — runs on an existing host |
| **Evaluation harness** | OpenTofu: ephemeral compute for eval runs |
| **Library** | none — not deployed |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| **OpenTofu** | declarative IaC in HCL, full provider ecosystem | default for new infra; the open Terraform | MPL-2.0, Linux Foundation — GA since 1.6 (2024), native state encryption |
| Terraform | same HCL/providers | an existing Terraform estate or a provider only it supports | BSL, IBM — source-available, not OSI |
| Pulumi | IaC in Python/TS/Go | infra logic wants a real language and tests | Apache-2.0 |

Config management (Ansible) is for the **host/OS** layer (bare-metal, VM bootstrap on your own hardware), not for cloud resources — a different plane from IaC. Kubernetes manifests are `ops-gen-kubernetes`, not IaC.

**Never:** local state on a team · `apply` without a reviewed `plan` · secrets hardcoded in HCL · hand-editing state · click-ops as the source of truth · adopting BSL Terraform for new work when OpenTofu fits.

## Testing

Validate (`tofu validate`), plan in CI on every PR, policy-check with OPA/`conftest` or `tflint`. Ephemeral integration: apply to a throwaway workspace, assert outputs, destroy. Never test against production state.
