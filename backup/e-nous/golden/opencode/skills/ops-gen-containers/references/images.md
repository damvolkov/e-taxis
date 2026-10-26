# images — building small, reproducible, safe

## Multistage

Separate what you need to *build* from what you need to *run*.

- `builder` stage: full toolchain, compile/install into a self-contained artifact (a venv, a binary).
- final stage: a minimal base, `COPY --from=builder` only the artifact. Build deps, caches and source-only files never reach the shipped image.
- Multiple builders are fine (e.g. one for wheels, one for frontend assets); the final stage stays thin.

## Base image

- `python:3.13-slim` for most services; `distroless` when you want no shell/package manager (smallest attack surface); full `bookworm` only when a build needs it (in the builder, not the runtime).
- **Pin by digest** (`@sha256:…`), not a floating tag — reproducibility and supply-chain safety.
- Fewer layers of provenance = fewer CVEs; scan the image (`trivy`, `grype`).

## Layer caching

Docker caches a layer until its inputs change, then invalidates everything after it. Order accordingly:

```
system packages         # changes rarely
COPY lockfile           # changes occasionally
install locked deps     # cached across code edits — the big win
COPY source             # changes constantly — keep it last
```

Copying the whole context before installing deps busts the dependency cache on every code change — the most common Dockerfile mistake.

## Non-root & least privilege

- Create a user (`useradd -u 1000`) and `USER` it before `CMD`; root in a container is root on a breakout.
- Drop capabilities, read-only root filesystem where possible, no `--privileged`.

## PID 1 & signals

- PID 1 has special duties: reap zombies, forward `SIGTERM`. A bare `CMD python app.py` as PID 1 may ignore signals → slow, ungraceful shutdown.
- Use **exec form** `CMD ["python", …]` (not shell form, which wraps in `/bin/sh -c`), and a real init (`tini`, or `docker run --init`) when the app doesn't handle signals itself.
- Graceful shutdown on `SIGTERM` ties into rollout drain → `sys-gen-scaling` `resilience.md`.

## Healthcheck

- A `HEALTHCHECK` (or the orchestrator's probe) lets the platform know the container is serving, not just running. In Kubernetes the probes supersede it → `ops-gen-kubernetes`.
