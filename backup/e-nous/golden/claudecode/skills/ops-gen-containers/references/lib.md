# lib — the container stack

What to reach for to build and run containers. Reach order: **Docker + BuildKit → Compose (local) → linters/scanners**; rootless via Podman where the daemon is unwanted. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The container stack × the nine software categories. It barely varies — the image is the image; what differs is what runs inside and whether it ships to a cluster.

| Category | Container stack |
|---|---|
| **API service** | Docker multistage → registry → `ops-gen-kubernetes` |
| **Async worker** | same image, different `CMD`; Compose locally |
| **ML pipeline** | GPU base image (CUDA) in the builder; slim runtime |
| **Agent system** | Docker multistage; Compose for local deps |
| **Voice runtime** | slim image, device access flags for local audio |
| **CLI tool** | single-stage or distroless binary image |
| **System script** | minimal image or none — runs on the host |
| **Evaluation harness** | Docker for reproducible eval runs |
| **Library** | no image — ships to an index (`pkg`) |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| Docker + BuildKit | build engine, layer cache, secrets/mounts | default image build | Apache-2.0 (engine) |
| Docker Compose | local multi-service topology | dev / self-hosted single node | Apache-2.0 |
| `hadolint` · `trivy`/`grype` | Dockerfile lint · image CVE scan | in CI before publishing | open source |
| Podman + Buildah | daemonless, rootless OCI builds | no-daemon / rootless requirement | Apache-2.0 |

Registries (GHCR, ECR, Artifact Registry) → `ops-gen-cloud`. Base images pinned by digest; GPU bases (`nvidia/cuda`) for ML runtimes.

**Never:** `latest` base tags · root as the container user · secrets baked into a layer · the whole context copied before dep install · Compose as a production orchestrator · a fat runtime carrying the build toolchain.

## Testing

Build in CI, scan the image, run the container's healthcheck, and smoke-test the entrypoint. Assert the image runs as non-root and starts on `SIGTERM`/stops cleanly.
