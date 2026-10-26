# workflow — state, plan, modules

## State

The state file maps declared resources to real ones. It is the most fragile part of IaC.

- **Remote backend** — S3+DynamoDB, GCS, Azure Blob, or an OpenTofu/Terraform-native backend; never local state on a team.
- **Locking** — the backend must lock so two `apply`s can't race and corrupt state.
- **Encryption** — state contains secrets (generated passwords, keys); encrypt at rest. OpenTofu adds native client-side state encryption.
- **Never hand-edit** — use `state mv`/`import`/`rm` commands, not a text editor. A corrupt state orphans live resources.

## Plan / apply cycle

```
write/change HCL → tofu plan (read the diff) → review in CI/PR → tofu apply (gated)
```

- `plan` shows create/update/**destroy**; a surprise `destroy` in a plan means stop and reconcile.
- Apply from CI on merge, not from a laptop; require the plan to be reviewed.
- `-target` and manual state surgery are break-glass, not routine.

## Modules

- One module = one composable unit (a network, a cluster, a database). Inputs are variables, outputs are what other modules consume.
- Parametrize environments (`dev`/`staging`/`prod`) with variable files or **workspaces** — same module, different inputs. Don't copy-paste per environment.
- Pin module and provider versions; a floating version is a non-reproducible build.
- Resist speculative modules — extract one when a second caller actually appears.

## Drift

Out-of-band changes (someone edited the console) make reality diverge from state. `plan` detects drift; policy is to reconcile through code, not to patch by hand — otherwise the next `apply` reverts or destroys the manual change.

## Secrets

Never hardcode secrets in HCL or commit them in state-readable form. Source from a secret manager (Vault, cloud KMS/secret store → `ops-gen-cloud`) and mark variables `sensitive`. Generated secrets in state are why the backend must be encrypted.
