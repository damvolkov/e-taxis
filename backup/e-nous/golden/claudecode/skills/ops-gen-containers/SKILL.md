---
name: ops-gen-containers
description: "Gen: Docker containers — multistage builds, pinned base, layer caching, non-root, PID 1/signals, config/secrets, Compose for local topology. Use when writing a Dockerfile or containerizing a service."
metadata:
  family: delivery
---

# ops-gen-containers

A container is a process with its filesystem and deps frozen — not a VM. This skill makes that image small, reproducible and safe. Owns Docker/OCI images and local Compose topology. Orchestration at scale → `ops-gen-kubernetes`; the scaling decision → `sys-gen-scaling`. The build/runtime stack → `references/lib.md`.

## Rules

1. **Multistage always.** A `builder` stage compiles/installs; the final stage copies only the artifact into a slim runtime — build tools never ship. → `references/images.md`
2. **Minimal, pinned base, non-root.** `slim`/`distroless`, pinned by digest; create and run as an unprivileged user; drop capabilities. Never `latest`.
3. **Order layers by volatility.** Least-changing first (system deps → locked deps → app code) so the cache survives a code edit; a lockfile copied before source caches the dependency layer. → `references/images.md`
4. **One concern per container.** The container runs one process; PID 1 must reap children and forward signals — use exec form `CMD` and a real init (`tini`/`--init`) when the process doesn't. → `references/images.md`
5. **Tiny build context.** `.dockerignore` excludes `.git`, caches, secrets, `.venv`; a fat context slows every build and leaks files.
6. **Config by env, secrets by mount.** 12-factor: configuration through environment, secrets injected at runtime (BuildKit secrets, mounted files) — never baked into a layer, layers are forever.
7. **Compose is for local, not production.** `compose.yml` describes the dev/self-hosted multi-service topology; production orchestration and scaling are Kubernetes. → `references/compose.md` · `ops-gen-kubernetes`

## Sample

```dockerfile
# builder — deps only, cached unless the lockfile changes
FROM ghcr.io/astral-sh/uv:0.8-python3.13-bookworm AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen                 # dependency layer, cached across code edits

# runtime — slim, non-root, copies only the venv + app
FROM python:3.13-slim-bookworm
RUN useradd -m -u 1000 app
COPY --from=builder /app/.venv /app/.venv
COPY app/ /app/app/
USER app
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8012"]
```

Deps are a cached layer before the code; the final image carries no build toolchain and runs as `app`, not root.

## References

- `references/images.md` — multistage, base choice, layer caching, non-root, PID 1/signals, healthcheck
- `references/compose.md` — local multi-service topology, profiles, dependency ordering, dev vs prod boundary
- `references/lib.md` — the stack: Docker/BuildKit, Compose, linters, and the rootless alternative
