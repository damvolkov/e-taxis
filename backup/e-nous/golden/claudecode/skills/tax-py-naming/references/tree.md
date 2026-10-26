# Paths

## The law

A module identifier is the concatenation of its path segments. Each folder contributes one term of the vocabulary; the file keeps the irreducible word.

```
src/e_voice/adapters/tts/kokoro.py
    └ package  └ layer   └ domain └ implementation
    = "the Kokoro TTS adapter of e-voice"
```

From which the single-word rule follows mechanically: **if a filename needs two words, a folder is missing, or the qualifier is already in the folder.**

| Wrong | Diagnosis | Right |
|---|---|---|
| `events/sample_adapter.py` | qualifier redundant with folder | `events/adapters.py` |
| `events/process_pool.py` | `process` is noise | `events/pool.py` |
| `adapters/api_client.py` | `api` redundant with `adapters/` | `adapters/client.py` |
| `core/exception_handler.py` | `handler` is implementation, not identity | `core/exceptions.py` |
| `components/parent_retriever.py` | missing `retrievers/` folder | `retrievers/parent.py` |

## Folder vocabulary

Folders are chosen from the lexicon, never invented.

| Folder | Role | Holds |
|---|---|---|
| `core/` | cross-cutting infra | settings, logger, lifespan, router, websocket, state, health |
| `config/` | modular settings | one file per domain, one `BaseSettings` each |
| `models/` | contracts | core, error, session, system, `<domain>` |
| `adapters/` | outer boundary | base, registry, client + subdomain (`stt/`, `tts/`) |
| `api/` | HTTP routes | one file per resource |
| `websockets/` | WS routes | mirrors `api/` |
| `operational/` | domain orchestration | controller, monitor, server, bench |
| `events/` | bus, concurrency | adapters, pool, monitor |
| `streaming/` | flow pipelines | audio, text, vad, transcriber |
| `middlewares/` | ASGI | base, files, swagger |
| `cli/`, `commands/` | CLI entry | run, config, session |
| `infra/`, `logic/`, `backends/` | library triad | see Tree B |

Reserved and stable everywhere: `base.py` (ABC/Protocol), `registry.py` (dispatch map), `main.py` (entrypoint), `settings.py`, `conftest.py`.

### `__init__.py` is not among them

A folder is a package because of its path, not because of a file: the tree is a **namespace package by default** and `__init__.py` is **banned**, at every depth, in `src/` and in `tests/`. Creating one is the cargo-cult of a language that dissolved the requirement in PEP 420.

It survives only in the exceptional case, and the case must be a tool that genuinely cannot resolve the tree without it:

- a build backend or plugin loader that enumerates regular packages only (`setuptools.find_packages`, some `importlib.metadata` entry-point scanners);
- a package-level runtime hook the tool can install nowhere else (`beartype.claw`, an `__init__` the loader itself executes);
- a distribution whose public surface must be the package rather than a module — the library archetype's `logic/api.py` stays the rule, the re-exporting `__init__` is the exception, declared where the packaging is configured.

In all three it holds **a docstring or the hook, nothing else**: no imports of siblings, no re-export chains, no logic, no constants. Anything else is deleted and the folder becomes what its path already says. → `proj-py-layout`

The subdomain pattern is what makes compound filenames unnecessary:

```
adapters/
├── base.py        contract
├── registry.py    dispatch
├── stt/
│   └── whisper.py implementation — one word, the brand
└── tts/
    ├── kokoro.py
    └── qwen.py
```

## Tree A — service (API, daemon)

```
e-<name>/
├── src/e_<name>/
│   ├── main.py            only place that knows the app; explicit registration
│   ├── core/              settings, logger, lifespan, router
│   ├── models/            core, error, <domain>
│   ├── api/               health, <resource>
│   ├── adapters/          base, registry, <domain>/<impl>.py
│   └── operational/       controller, monitor
└── tests/
    ├── conftest.py        session-wide
    ├── resources/         assets, outside the mirror
    ├── unit/
    │   ├── conftest.py    fakes, mocks
    │   └── e_<name>/      exact mirror of src/e_<name>/
    └── integration/
        └── e_<name>/      same mirror, another tier
```

## Tree B — library (hexagonal triad)

```
e-<name>/
├── src/e_<name>/
│   ├── main.py
│   ├── infra/             inward: contracts, no logic — protocols, errors, formats, io
│   ├── logic/             pure core — api (public surface), encoder
│   └── backends/          outward: interchangeable — base, registry, native/, msgspec/
└── tests/
    ├── conftest.py
    ├── resources/
    ├── unit/e_<name>/     mirror, hierarchy preserved: backends/native/test_toml.py
    └── benchmark/
```

Package name is the repo with hyphens turned into underscores: `e-voice` → `e_voice`.

## The two anti-patterns, which are one

```
tests/unit/test_evoice_stt_adapter.py        path collapsed into the name
tests/unit/e_heed/daemon/adapters/stt/test_evoice.py

tests/unit/e_serde/backends/test_native_toml.py
tests/unit/e_serde/backends/native/test_toml.py

src/e_rag/components/parent_retriever.py     same fault, in src
src/e_rag/retrievers/parent.py
```

One cause: hierarchy pushed into an identifier instead of into the filesystem.

## The import

The path is the name, and an import is that name read from the root. Two corollaries, both absolute:

- **Relative imports are banned.** `from .x import y` hides the path behind the file's position; the same symbol is reached as `from pkg.mod import y`, which states who the module is. A refactor that moves the importer silently rebinds a relative path — never an absolute one.
- **Module level only.** An import inside a function body — deferred, lazy, "to avoid the cycle" — is banned outright. The import graph *is* the architecture: a cycle means two concepts share a module that was never split, and hiding the edge fixes nothing. The only exception is one Damien explicitly names, and then it carries a `###` line saying so.

```
ops/eval/__init__.py     # gone — the folder is a namespace; the path says what it is
ops/eval/refresh.py      # the shared function — it has its own name, its own path
```

## Verification

The rule is mechanical, so it is checked, not eyeballed.

```bash
# relative imports — zero matches by law
grep -rn "^\(from\| *from\) \." --include="*.py" src/

# imports not at module level — zero matches by law
grep -rnE "^[[:space:]]+(from|import) " --include="*.py" src/

# __init__.py — zero by law; every hit must name the tool that forces it
find src tests -name "__init__.py"

# multi-word modules in src/
find src -name '*_*.py' ! -name '__*' -print

# parity orphans, both directions
comm -3 \
  <(find src -name '*.py' ! -name '__*' | sed 's|^src/||; s|\.py$||' | sort) \
  <(find tests/unit -name 'test_*.py' | sed 's|^tests/unit/||; s|/test_|/|; s|\.py$||' | sort)
```
