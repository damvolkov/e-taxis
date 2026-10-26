# lib — the scaffold and structure stack

What holds a layout together as tooling. Reach order: `uv` (workspace + backend) → `hatchling` + `uv-dynamic-versioning` (build) → `tach` (import boundaries) → `prek` (git hooks). Build and publish proper are `pkg`; this list is the structure-enforcing tools. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The scaffold stack barely varies — the layout differs, the tools that enforce it do not.

| Category | Structure tooling |
|---|---|
| **API service** | `uv` · `hatchling` · `tach` (api→core→adapters layers) |
| **Async worker** | same; `tach` guards the worker/domain split |
| **ML pipeline** | same; `tach` guards pipeline→component→core |
| **Agent system** | same; `tach` guards turn/sentinel/tools boundaries |
| **Voice runtime** | same; `tach` guards streaming/adapters/events |
| **CLI tool** | `uv` · `hatchling`; `[project.scripts]` entrypoint |
| **System script** | minimal — `uv` only, often no package |
| **Evaluation harness** | `uv` · `hatchling`; regression tier under `tests/evaluation/` |
| **Library** | `uv` · `hatchling` + `uv-dynamic-versioning`; `tach` guards infra←logic←backends |

## The stack

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `uv` | workspace, deps, run, build backend front-end | every project — the base | Apache-2.0/MIT, Astral |
| `hatchling` + `uv-dynamic-versioning` | build backend + Git-tag PEP 440 versions | packaging any distributable → `pkg` | MIT |
| `tach` | declare and check import-layer boundaries | any project with layers (all of them) | MIT |
| `prek` | run the git hooks of `.pre-commit-config.yaml` (Rust; drop-in for `pre-commit`) | every repo — the base hooks → `hooks.md` | MIT |
| `copier` | scaffold a new project from a template, re-appliable | starting a repo from the archetype | MIT — vs the house `scripts/init.py` |

The house scaffolds with a `scripts/init.py` run via `make init` (→ `ops-gen-make`); `copier` is the reach-for alternative when templates must update in place. Every package in the scaffold is a **namespace package**: no `__init__.py` at any depth. It appears only in the exceptional, tool-forced case, and then holds a docstring or the hook, never logic → `tax-py-naming`.

**Never:** the Python `pre-commit` (→ `prek`) · an `__init__.py` no tool forces · a flat `<pkg>/` at repo root instead of `src/<pkg>/` · a layout folder outside the lexicon (→ `tax-py-naming`) · an import that violates `tach.toml` · logic in a layout with no test mirror · versions hand-edited instead of Git-tag derived.

## Testing

`tach check` in CI proves the import graph; `make check` runs it beside lint/type/test; `make hooks` runs the prek hooks over every file. A new module without its `tests/` mirror fails the parity check (→ `tax-py-naming` verification). The scaffold itself is validated by building the template and running its `make ci`.
