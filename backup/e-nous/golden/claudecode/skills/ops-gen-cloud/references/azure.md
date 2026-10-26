# azure — capability → service map

Read the capability, take the service. Prefer open-interface services (✓ portable) to keep the escape hatch.

| Capability | Azure service | Portable | Note |
|---|---|---|---|
| Managed Kubernetes | AKS | ✓ (K8s API) | the portable default for compute |
| Serverless containers | Container Apps | ~ | KEDA-based scale-to-zero; light lock-in |
| Functions | Azure Functions | ✗ | event glue |
| Object storage | Blob Storage | ✓ (S3 via adapters) | native API differs; use an S3 gateway for portability |
| Relational DB | Azure Database for PostgreSQL | ✓ (Postgres wire) | flexible server |
| Cache | Azure Cache (Valkey/Redis) | ✓ (Redis proto) | |
| Queue / streaming | Service Bus / Event Hubs | Bus ✗ · Event Hubs ✓ | Event Hubs speaks the Kafka API |
| Vector | AI Search / pgvector | ~ | pgvector stays portable |
| Load balancer | Application Gateway / Load Balancer | ✓ | L7 wired to AKS |
| Secrets | Key Vault | ✗ | reach via External Secrets Operator |
| Identity | Entra ID + Workload Identity | ✗ | per-pod identity, OIDC — no static secrets |
| CDN / edge | Azure Front Door / CDN | ✗ | latency/reach answer (trigger #8) |
| Registry | ACR | ✓ (OCI) | push from `ops-gen-containers` |

## Lock-in & cost watch

- Functions + Service Bus + Cosmos DB is locked-in; AKS + Blob + PostgreSQL is portable (Event Hubs' Kafka API keeps streaming portable).
- Egress and cross-region are the cost drivers — stay regional.
- Workload Identity federates a K8s ServiceAccount to Entra — no client secrets.
- Provision with `ops-gen-iac` (the azurerm provider).
