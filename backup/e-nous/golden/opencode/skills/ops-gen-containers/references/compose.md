# compose — local multi-service topology

Compose describes the **development and self-hosted** topology: the app plus its dependencies (Valkey, a broker, a database) wired together on one host. It is not a production orchestrator — that boundary is the whole point.

## Shape

```yaml
services:
  api:
    build: .
    ports: ["8012:8012"]
    environment: [ "VALKEY_URL=redis://cache:6379" ]
    depends_on:
      cache: { condition: service_healthy }
  cache:
    image: valkey/valkey:8-alpine
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
```

## What Compose is for

- **Local dev / self-hosted single node** — bring up the whole stack with one command.
- **Dependency ordering** — `depends_on` + `condition: service_healthy` so the app waits for its backing services.
- **Profiles** — `--profile` to toggle optional services (observability, a seed job) without separate files.
- **Reproducible env** — the same image and wiring every developer runs.

## What Compose is NOT for

- Multi-node scaling, self-healing, rolling updates, autoscaling → Kubernetes (`ops-gen-kubernetes`).
- Production secrets management, network policy, RBAC → the orchestrator/platform.

## The dev → prod boundary

Compose and Kubernetes describe the same *containers* but different *planes*: Compose is one host for iteration; Kubernetes is the cluster for scale and resilience. Keep the image identical across both; only the orchestration layer differs. Deciding you need the cluster at all → `sys-gen-scaling`.
