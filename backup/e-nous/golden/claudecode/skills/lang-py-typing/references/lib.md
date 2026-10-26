# lib — the typing enforcement stack

The `typing` module is builtin; the enforcers are not. Two gates: **static** (whole program, at CI/edit time) and **runtime** (at the call, in production). Reach order: builtin `typing` for the annotations → `ty` static → `beartype` runtime. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The enforcement target × the nine software categories. The discipline is uniform — what changes is where `@beartype` sits.

| Category | Static · runtime enforcement |
|---|---|
| **API service** | `ty`/`pyright` in CI · `beartype` on services, stores, request models |
| **Async worker** | `ty` · `beartype` on task handlers and payload boundaries |
| **ML pipeline** | `ty` · `beartype` on pipeline stages, processors (catches dtype/shape drift early) |
| **Agent system** | `ty` · `beartype` on tools, adapters, message models |
| **Voice runtime** | `ty` · `beartype` on frame/buffer boundaries (O(1), safe on the hot path) |
| **CLI tool** | `ty` · `beartype` on command entrypoints |
| **System script** | `ty` · `beartype` optional |
| **Evaluation harness** | `ty` · `beartype` on metric/scoring functions |
| **Library** | `ty` **and** `pyright` (match consumers' checker) · `beartype` on the public API |

## Primary tools

| Tool | Gate | Reach for it when | License · maturity |
|---|---|---|---|
| `typing` (+ `collections.abc`) | the annotations themselves | always — builtin | stdlib |
| `ty` | static, Rust, incremental | fast whole-program checking, CLI + LSP | MIT, Astral — **beta** (0.0.x, no stable API yet; stable eyed 2026) |
| `pyright` | static, stable | the CI gate today while `ty` is beta; libraries (consumer parity) | MIT, Microsoft — mature |
| `beartype` | runtime, O(1) | enforce contracts at the call, in production | MIT — no deps, active (~0.23) |

Alternatives named only in prose: `mypy` (the reference static checker, slower); `typeguard` (runtime, richer errors, not O(1)). Apply `beartype` per class with `beartype.claw` or `decorate_methods(beartype)`; never hand-write `isinstance` gauntlets it generates.

**Never:** `# type: ignore` · bare `Any` off a third-party edge · `Optional`/`List`/`Union` (use `X | None`, `list`, `|`) · a `runtime_checkable` Protocol where `beartype` should enforce the real signature · shipping a library checked by only one static checker.

## Testing

`ty`/`pyright` run in CI as a blocking gate. Property tests (`hypothesis`) that pass malformed values confirm `beartype` raises at the boundary. Assert `assert_type(...)`/`reveal_type(...)` expectations in a typing-test module so annotation regressions fail loudly.
