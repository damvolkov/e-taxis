# lib — the task-runner toolchain

Make is the front door; these are what its targets wrap. The wrapped tools have their own skills — this list is only what a Makefile orchestrates. Reach order: GNU `make` (present everywhere) as the runner, `uv` as the Python backend most targets call. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The task-runner stack × the nine software categories — what the targets wrap.

| Category | Wrapped by the targets |
|---|---|
| **API service** | `uv` · ruff · ty · pytest · docker compose (`up`/`down`/`logs`) |
| **Async worker** | `uv` · pytest · docker compose; a `worker` run target |
| **ML pipeline** | `uv` · pytest · data/train scripts (`scripts/*.py`) |
| **Agent system** | `uv` · pytest · compose for local deps |
| **Voice runtime** | `uv` · device/run scripts · compose |
| **CLI tool** | `uv` · pytest · a `build`/`publish` target (no `up`/`down`) |
| **System script** | bash lines and `scripts/*.sh`; minimal |
| **Evaluation harness** | `uv` · pytest `-m benchmark` · eval scripts |
| **Library** | `uv` · pytest · `build`/`publish` (`pkg`); no docker |

## The stack

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| GNU `make` | the task runner: phony targets, help, arg forwarding | any repo — the universal front door | GPL, ubiquitous |
| `uv` | the Python backend most recipes call (`uv run …`, `uv sync`) | every Python task target | Apache-2.0/MIT, Astral |
| ruff · ty · tach · pytest · `prek` | the gate tools targets wrap (`lint`/`type`/`arch`/`test`/`hooks`) | their own skills own usage; Make only invokes | open source |
| docker compose | the `up`/`down`/`build`/`logs` targets → `ops-gen-containers` | local multi-service stack | Apache-2.0 |

Alternative runner: `just` (a purpose-built command runner, cleaner syntax, no build-system baggage) — reach for it when the repo wants a task runner without Make's file-target semantics; Make stays the default for ubiquity and zero install.

**Never:** put real logic in makefile escapes (use a script) · a non-phony command target · a hand-maintained help · wrap what the IDE already does inline · reimplement a tool Make should just call.

## Testing

A Makefile is exercised, not unit-tested: `make check` in CI is the proof the targets run. Keep `ci` an alias of the pipeline's steps so a green `make ci` locally predicts a green pipeline.
