# resilience — designing for failure

At N nodes, failure is normal, not exceptional. Every remote call can be slow, fail or be duplicated.

## Retries — with backoff and jitter

- Retry only **idempotent** or safe-to-repeat operations.
- Exponential backoff + **jitter** (randomized delay) — synchronized retries cause thundering herds.
- Cap attempts and total time; a retry budget prevents retries from amplifying an outage.
- In Python: `tenacity`/`stamina` (→ `lang-py-lifecycle` owns the retry lib).

## Idempotency

- Design writes so repeating them is harmless: idempotency keys, upserts, dedup on a stable id.
- Required wherever a retry, a queue redelivery or a replica retry can double an effect.

## Circuit breaker

- After repeated failures to a dependency, **open** the circuit: fail fast instead of piling on.
- Half-open probes test recovery before closing. Protects both caller (latency) and callee (load).

## Backpressure

- A fast producer must not overwhelm a slow consumer: bounded queues, rejected/shed load, `429`/`503` with `Retry-After`.
- The in-process mechanism (bounded channels) → `conc-py-async`; here it is a system-level contract between services.

## Health checks

- **Liveness** — restart if the process is wedged. **Readiness** — remove from the load balancer until able to serve. **Startup** — grace for slow boots.
- Kubernetes probes wire these → `ops-gen-kubernetes`.

## Graceful shutdown

- On `SIGTERM`: stop accepting, drain in-flight work, close connections, then exit — within the platform's termination grace period.
- Combined with readiness, this makes rollouts and scale-down lossless.

## Timeouts everywhere

- Every remote call has a deadline; unbounded waits turn one slow dependency into a cascading stall. Deadline propagation across a call chain keeps the whole path bounded.
