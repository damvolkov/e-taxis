# lib — the modeling stack

The single authority on what to import for modeling data, state and errors — and, more often than not, the answer is **nothing**. Sum types, Option, newtypes and flat state machines are all builtin: `type X = A | B`, `match`, `T | None`, `NewType`, `Annotated`, `StrEnum` + a frozen mapping. A library earns its place only for the heavier forms: full railway/monadic composition, statecharts, and C-backed functional combinators.

This skill's patterns are library-agnostic; this file is the one place vendors are named. Order of reach: **builtin → the async twin → the specialized library, only when its shape is the point.** Dates from the September 2026 survey; re-verify before pinning → `flow-gen-research`.

## By software category

The matrix: the skill's libbed targets × the nine software categories, cells = the typical library. `·` = builtin (the honest answer for most cells) · `⟳` = reach for the async form. **Sum types, newtype and Option are `·` builtin in every category** (`match`, `StrEnum`, `NewType`, `T | None`) — they never appear below because they never take a library.

| Category | Result | State machine | Functional combinators |
|---|---|---|---|
| **API service** | · Ok/Err | · table | · |
| **Async worker** | `returns` ⟳ | `python-statemachine` ⟳ | `cytoolz` |
| **ML pipeline** | · Ok/Err → `returns` | · table | `cytoolz` |
| **Agent system** | `returns` ⟳ | `python-statemachine` ⟳ | · |
| **Voice runtime** | · Ok/Err (no exc, hot path) | `python-statemachine` | · |
| **CLI tool** | · Ok/Err | — | · |
| **System script** | · Ok/Err (fail with exact cause) | — | · |
| **Evaluation harness** | · Ok/Err → `returns` | · table | `cytoolz` |
| **Library** | · Ok/Err (typed errors) | · table | · |

Read it with `application_map.md` (same target × category axes, intensity instead of vendor): that says *whether* a pattern applies, this says *with what*. The through-line: the more a category **decides** (worker, agent, ML, eval), the sooner a library earns its place; the more it just moves bytes (script, CLI, thin API), the longer builtin wins.

## What to reach for, and what not

| Pattern | Async | Sync | Builtin baseline (default) | Library — only when |
|---|---|---|---|---|
| Sum types / ADT / match | — | — | `type X = A\|B`, `match`, `StrEnum` | **never** — the language is complete here |
| Option / absence | same | same | `T \| None` + walrus | chaining many nullable steps → `returns.Maybe` |
| Result / railway | `returns` (`FutureResult`) | Ok/Err dataclass · `returns` | Ok/Err frozen dataclass (N5) | deep chains, monadic `.bind`/`.map`, `@safe`, HKT, DI → `returns` |
| Newtype / validation | — | — | `NewType` · `Annotated[…, AfterValidator]` (Pydantic) | rich validation is Pydantic's job → `lang-py-datamodel` |
| State machine | `python-statemachine` (async engine) · `transitions.AsyncMachine` | `python-statemachine` · builtin table | `StrEnum` + `Final` transition mapping | statecharts: compound/parallel/history, guards, hooks, diagrams |
| Functional combinators | `returns` | **`cytoolz`** (C) · `toolz` · `funcy` | `functools` · `operator` · `itertools` → `para-py-iteration` | `compose`/`curry`/`pipe` beyond stdlib → `cytoolz` |

## Notes per choice

- **`returns`** (dry-python, v0.28, Feb 2026) — the complete railway toolkit: `Result`/`Maybe`/`IO`/`Future`/`RequiresContext`, `.bind`/`.map`, `@safe`, HKT. Reach for it when hand-rolled `bind` combinators multiply or you need async railways. Heavy and opinionated — do not import it to replace a two-branch `match`.
- **`result` (rustedpy)** — **ARCHIVED 2026-06-25, read-only. Do not adopt for new code.** Its niche (a plain Ok/Err) is already your N5 baseline.
- **`python-statemachine`** (fgmacedo, v3.x, py3.9–3.14) — statecharts with one async/sync API (the engine auto-detects async callbacks), DI into callbacks, diagram generation. The default when you outgrow a flat table.
- **`transitions`** (`AsyncMachine`) — mature, HSM support; reach for it only if you already use its ecosystem.
- **`cytoolz`** — Cython implementation of `toolz`, 2–5× faster, C API. Rust/C-backed mandate applies: prefer it over pure `toolz` for `compose`/`curry`/`pipe`/`groupby`. "Alive but inactive" — stable, low churn. Iterable operators themselves live in → `para-py-iteration/lib.md`; take only the composition helpers from here.

## Result — async (first) · sync

| Concern | Async (first) | Sync |
|---|---|---|
| wrap a fallible call | `@future_safe` (`returns`) | `@safe` (`returns`) · manual `Ok/Err` |
| chain steps, short-circuit | `FutureResult.bind` | `Result.bind` · hand-rolled `bind` |
| absence chain | `returns.Maybe` | `T \| None` + walrus |
| collect many results | `[r async for r in …]` then partition | comprehension + partition by `Ok`/`Err` |

## Cross-skill

- Selecting a handler / transition = dispatch, not modeling → `para-py-dispatch` (`ovld`, `plum-dispatch`, frozen mapping).
- Iterating/streaming the values → `para-py-iteration` (`asyncstdlib`, operators, `cytoolz` iterable ops).
- Scoping and releasing resources, exception discipline at the boundary → `lang-py-lifecycle`.
- Rich model validation and serialization → `lang-py-datamodel`.

**Never:** import `returns` to dress a single `if`/`match`; adopt archived `rustedpy/result`; build an `Option` class where `T | None` reads clean; use pure `toolz` when `cytoolz` is available.
