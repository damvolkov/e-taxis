# config — namespaces, config, secrets, access

## Namespace

A virtual cluster: scopes names, RBAC, resource quotas and NetworkPolicy. Split by environment or team (`prod`, `staging`, `team-x`). Quotas (`ResourceQuota`, `LimitRange`) cap what a namespace can consume.

## ConfigMap

Non-secret configuration decoupled from the image: env values, config files. Mount as env vars or as files. Changing a ConfigMap does not restart Pods — roll the Deployment (or use a reloader) to pick it up.

## Secret

Sensitive values (tokens, keys, passwords).

- **Secrets are base64-encoded, not encrypted** at rest by default — anyone with API/etcd access reads them. Enable etcd encryption-at-rest, and prefer an external manager.
- Back with **sealed-secrets** (encrypted in git) or an external store (External Secrets Operator → Vault/cloud secret managers → `ops-gen-cloud`).
- Never commit a raw `Secret` manifest; never bake secrets into the image (→ `ops-gen-containers`).

## RBAC & ServiceAccount

- Every Pod runs as a `ServiceAccount`; grant it only the API permissions it needs via `Role`/`RoleBinding` (namespaced) or `ClusterRole` (cluster-wide).
- Least privilege: no default admin tokens, no `cluster-admin` on a workload SA.
- This is the cluster-plane instance of the "right plane of resolution" — authz for infra actions belongs here, not in app code.
