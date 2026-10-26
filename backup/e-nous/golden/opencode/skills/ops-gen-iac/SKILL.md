---
name: ops-gen-iac
description: "Gen: infrastructure as code — declarative, versioned, plan-before-apply; remote encrypted state; modules; OpenTofu over Terraform. Use when provisioning cloud or cluster infrastructure."
metadata:
  family: delivery
---

# ops-gen-iac

Infrastructure declared as code, reviewed and applied like software. Owns provisioning — the cloud/cluster/network/DB *resources* — not what runs on them. Deploying onto the provisioned cluster is `ops-gen-kubernetes`; the scaling decision that justifies the infra is `sys-gen-scaling`; provider specifics are `ops-gen-cloud`. The tooling → `references/lib.md`.

## Rules

1. **Declarative, versioned, reviewed.** Infra lives in git as desired state; changes are pull-requested and planned. No click-ops as the source of truth — the console is for reading, not for changing.
2. **OpenTofu over Terraform for new work.** Same HCL and providers, but MPL-2.0 under the Linux Foundation vs Terraform's BSL under IBM — the open license wins for the `e-` prefix. → `references/lib.md`
3. **Plan before apply, always.** Read the diff; `apply` is never the moment to discover a `destroy`. Gate `apply` behind review/CI, never run it blind.
4. **State is the source of truth and a liability.** Remote, locked, encrypted backend — never local state on a team, never edit it by hand. A lost or corrupt state orphans real resources. → `references/workflow.md`
5. **Modules for reuse, not for cleverness.** Compose small, single-purpose modules; parametrize per environment with variables/workspaces. No speculative abstraction — a module earns its place. → `references/workflow.md`
6. **Idempotent and immutable.** Re-applying converges to the same state; prefer replace over in-place mutate; reconcile drift, never leave out-of-band changes.
7. **Provision ≠ configure ≠ orchestrate.** IaC creates the cluster/network/DB; Kubernetes/Helm deploys onto it; app config is runtime. Don't blur the layers — each is the cheapest plane for its concern (AGENTS.md rule #19). → `ops-gen-kubernetes`

## Sample

```hcl
terraform {
  backend "s3" {                          # remote, locked, encrypted — never local
    bucket = "eager-tfstate"
    key    = "prod/cluster.tfstate"
    encrypt = true
    dynamodb_table = "tfstate-lock"
  }
}

module "cluster" {                        # small, parametrized, reusable
  source       = "./modules/k8s-cluster"
  environment  = "prod"
  node_pools   = var.node_pools
}
```

Runs identically under OpenTofu (`tofu plan`/`tofu apply`); the backend is remote and locked so concurrent applies can't corrupt state.

## References

- `references/workflow.md` — state backends, plan/apply, modules, workspaces, drift, secrets
- `references/lib.md` — the stack: OpenTofu/Terraform, Pulumi, the IaC-vs-config boundary
