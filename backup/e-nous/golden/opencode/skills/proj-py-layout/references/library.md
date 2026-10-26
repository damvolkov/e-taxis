# library — importable package (hexagonal triad)

No app, no entrypoint that runs a server — a package other code imports. The house shape is a three-layer hexagon, modeled on `e-serde`. Evaluation harnesses fold in here: a library plus an `evaluation/` test tier.

```
src/e_<name>/
├── __main__.py           # optional: python -m e_<name> for a demo/CLI
├── infra/                # inward: contracts, no logic — protocols, errors, formats, io
├── logic/                # the pure core — api (public surface), the algorithm
└── backends/             # outward: interchangeable — base, registry, native/, msgspec/
tests/
├── unit/e_<name>/        # mirror; backends/native/test_toml.py, hierarchy preserved
└── benchmark/            # a library earns its keep on numbers
```

## Non-negotiables

- **Dependencies point inward** — `backends/` and the public API depend on `infra/`'s contracts; `infra/` depends on nothing. The pure core (`logic/`) has no I/O → `arch-py-hexagonal`.
- **The public surface is one module** — `logic/api.py` is what consumers import; everything else is private structure. A package `__init__` re-exporting it is the exceptional case, not the alternative: namespace package by default → `tax-py-naming`.
- **Backends are swappable and registered** — `backends/base.py` (Protocol) + `backends/registry.py` + one folder per implementation; add a backend without touching the core.
- **Never configure the host** — a library uses `structlog.get_logger()` but never calls logging `setup()`; it forces no framework, no event loop policy, no global config on its consumer → `obs-py-logging`.
- **Force no dependency** — prefer stdlib in the public path so importing the library costs the consumer nothing; heavy deps stay behind a backend.
- **Build & publish** — `hatchling` + `uv-dynamic-versioning`; versioning and release are `pkg`.
- **Evaluation harness variant** — add `tests/evaluation/regression/<domain>/` with polars-based regression and its own `run_experiment.py`; the eval method is `test-py-tdd`, the metrics `obs`.
