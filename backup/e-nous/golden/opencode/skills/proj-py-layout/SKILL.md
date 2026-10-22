---
name: proj-py-layout
description: "Python: project layout per system type — src layout, settings, DI, lifespan, tach boundaries, prek hooks; scaffolds for API, voice, agent, ML/RAG, CLI, library. Use when structuring a project."
metadata:
  family: design
---

# proj-py-layout

The skeleton a project is born with: which directories a given system type needs, and the wiring that is not optional. Owns the layout decision and the composition non-negotiables. The path law, folder lexicon and reserved filenames are `tax-py-naming` (referenced, never repeated); the test tree is `test-py-tdd`; build and versioning are `pkg`. Six archetypes, one per reference; a system maps to exactly one.

## Rules

1. **src layout; package = repo underscored.** `src/e_<name>/`, the package is the repo name with hyphens turned to underscores; `tests/` mirrors `src/` from the root. Folder names come from the lexicon → `tax-py-naming`. No `__init__.py` by default — namespace tree; a tool-forced one holds a docstring or its hook, never logic → `tax-py-naming`. Every import absolute from the root, `from .` banned; imports at module level only — inside a function or lazy to dodge a cycle is banned, the cycle is the layout bug → `tax-py-naming`.
2. **Pick the archetype, take its scaffold.** API, voice, agent, ML/RAG, CLI or library — each has a fixed skeleton; async worker folds into API, evaluation harness into library. → the references below.
3. **One entrypoint, explicit registration.** `main.py`/`__main__.py` is the only module that knows the app; routers, commands and handlers are plain functions registered there, never bound by a decorator. → `arch-py-hexagonal`
4. **Settings compose by domain.** `config/<domain>.py` — one `BaseSettings` each — composed by multi-inheritance in `core/settings.py`, imported everywhere as `from <pkg>.settings import settings as st`. → `arch-py-hexagonal`
5. **Lifespan and DI live at the edges.** Resource startup/shutdown in `core/lifespan.py`; request-scoped wiring in `api/deps.py`; the composition root binds ports to adapters. → `arch-py-hexagonal` · `lang-py-lifecycle`
6. **Enforce boundaries and gates before the commit lands.** `tach.toml` declares which layer may import which (adapters → core, never core → api); `prek` runs the house hooks — ruff, ty, tach, zizmor, gitleaks — on every commit, installed by `make install`. `prek`, never the Python `pre-commit`: same config, Rust-backed. → `references/hooks.md` · `references/lib.md`
7. **`tests/`, `resources/`, `benchmark/` from line one.** Every layout ships the mirrored test tree with `resources/` and `benchmark/` present, empty if unused. → `test-py-tdd`

## Sample

```
e-<name>/
├── src/e_<name>/
│   ├── __main__.py          # python -m e_<name> — the only place that knows the app
│   ├── core/                # settings, logger, lifespan, (deps)
│   │   └── settings.py      # class Settings(CoreSettings, ApiSettings, …)
│   ├── config/              # one BaseSettings per domain (core, api, models…)
│   ├── models/              # contracts: core, error, <domain>
│   ├── adapters/            # boundary: base, registry, <domain>/<impl>.py
│   └── <archetype layer>/   # api/ · streaming/ · daemon/ · pipelines/ · cli/ · logic/
├── tests/                   # mirror of src/ + resources/ + benchmark/  → test-py-tdd
├── tach.toml                # import-layer boundaries
├── .pre-commit-config.yaml  # prek hooks → references/hooks.md
├── pyproject.toml           # hatchling + uv-dynamic-versioning → pkg
└── Makefile                 # one-word tasks → ops-gen-make
```

`core`/`config`/`models`/`adapters` are the shared spine; the archetype adds its own layer on top. Everything below `src/e_<name>/` is copied character-for-character into `tests/<tier>/e_<name>/`.

## References

- `references/api.md` — API service (and async worker): api/, websockets/, deps, middlewares, lifespan
- `references/voice.md` — voice runtime: streaming/{stt,tts}, adapters/{stt,tts}, events, realtime WS
- `references/agent.md` — agent system / semi-deterministic graph: daemon turn+sentinel, tools, MCP config
- `references/ml.md` — ML/RAG pipeline: pipelines, components/retrievers, operational, optional api
- `references/cli.md` — CLI tool: cli/commands, the cli-only layout, rich console
- `references/library.md` — importable package: the hexagonal triad infra/logic/backends
- `references/hooks.md` — the house git hooks: the base `.pre-commit-config.yaml`, prek, stages, install
- `references/lib.md` — the scaffold stack: tach, prek, hatchling + uv-dynamic-versioning, copier
