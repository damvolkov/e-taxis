# selfhosted — the own-hardware baseline

Damien runs his own models on his own hardware. This is the default plane; cloud is the reach when scale or availability forces it. All open, all portable, all on the standard interfaces the provider maps also target.

| Capability | Self-hosted (open) | Interface it speaks |
|---|---|---|
| Container orchestration | **k3s** (or full k8s) | Kubernetes API |
| Object storage | **MinIO** / SeaweedFS | S3 API |
| Relational DB | **PostgreSQL** | Postgres wire |
| Cache / KV | **Valkey** | Redis protocol |
| Queue / streaming | **NATS** (JetStream) / **Redpanda** | NATS / Kafka API |
| Vector store | **Qdrant** / pgvector | own / SQL |
| Load balancer / gateway | **Traefik** / Envoy | Gateway API, HTTP |
| Secret manager | **Vault** (OSS) / sealed-secrets | Vault API / K8s |
| Ingress from home | **frp** / cloudflared tunnel | reverse tunnel |
| TLS | **cert-manager** + Let's Encrypt | ACME |
| Observability | **Prometheus + Grafana + Loki** | OpenMetrics/OTLP |
| CI/CD | **Forgejo/Gitea Actions** / Woodpecker | git |

## Why self-host

- **Cost** — fixed hardware beats per-hour managed services at steady load.
- **Control & data residency** — models, data and secrets never leave the premises.
- **Portability** — every choice speaks a standard interface, so a later lift to a managed cloud is a config change, not a rewrite.

## When to leave it

- Elastic/bursty load beyond the hardware (trigger #6, `sys-gen-scaling`).
- Global reach / multi-region latency (trigger #8).
- Availability guarantees a single site can't meet (trigger #5).

Reaching a managed service is a plane decision, not a default; map the capability to the provider references only when one of these forces it.
