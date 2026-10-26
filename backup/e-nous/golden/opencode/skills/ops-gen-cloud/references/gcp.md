# gcp — capability → service map

Read the capability, take the service. Prefer open-interface services (✓ portable) to keep the escape hatch.

| Capability | GCP service | Portable | Note |
|---|---|---|---|
| Managed Kubernetes | GKE (Autopilot/Standard) | ✓ (K8s API) | strongest managed K8s; Autopilot removes node ops |
| Serverless containers | Cloud Run | ~ | container-native, scale-to-zero; light lock-in |
| Functions | Cloud Functions | ✗ | event glue |
| Object storage | Cloud Storage | ✓ (S3-compatible API) | interoperable with S3 tooling |
| Relational DB | Cloud SQL / AlloyDB (Postgres) | ✓ (Postgres wire) | AlloyDB faster, more proprietary |
| Cache | Memorystore (Valkey/Redis) | ✓ (Redis proto) | Valkey option |
| Queue / streaming | Pub/Sub | ✗ | managed, scalable; proprietary API |
| Vector | Vertex Vector Search / pgvector | ~ | pgvector stays portable |
| Load balancer | Cloud Load Balancing | ✓ | global L7; wired to GKE |
| Secrets | Secret Manager | ✗ | reach via External Secrets Operator |
| Identity | IAM + Workload Identity | ✗ | per-pod identity, OIDC — no static keys |
| CDN / edge | Cloud CDN | ✗ | latency/reach answer (trigger #8) |
| Registry | Artifact Registry | ✓ (OCI) | push from `ops-gen-containers` |

## Lock-in & cost watch

- Cloud Run + Pub/Sub + Firestore is convenient but locked-in; GKE + Cloud Storage + Cloud SQL(Postgres) is portable.
- Egress and cross-region traffic dominate cost — keep it regional.
- Workload Identity binds a K8s ServiceAccount to a GCP identity — no downloaded keys.
- Provision with `ops-gen-iac` (the Google provider).
