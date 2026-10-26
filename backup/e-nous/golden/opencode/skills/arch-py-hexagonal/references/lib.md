# lib — the DI / wiring stack

The single authority on what to import for dependency injection, and what never to. This skill's patterns are library-agnostic; this file is the one place vendors are named. The honest default for most projects is **import nothing** — constructor injection plus a composition root is the whole pattern. Reach for a container only when the graph is deep and scoped across many entrypoints.

Order of reach: **constructor injection (builtin) → framework-native → standalone container.** Dates are from the September 2026 survey; re-verify before pinning → `flow-gen-research`.

## By software category

The matrix: this skill's one libbed target — **DI / wiring** — across the nine software categories. The other macro patterns take no vendor here: **ports = `·` builtin `Protocol` in every category**; **repository backend → `data-py-*`**; **pipeline/middleware → the framework's own registry**. `·` = builtin constructor injection · `⟳` = async-scoped.

| Category | DI / wiring |
|---|---|
| **API service** | framework `Depends` ⟳ (request-scoped) |
| **Async worker** | `dishka` ⟳ (app/job scopes, generator finalization) |
| **ML pipeline** | `dishka` ⟳ / · ctor injection at the root |
| **Agent system** | `dishka` ⟳ (session scope) / · ctor injection |
| **Voice runtime** | · ctor injection (light, latency-sensitive; no container in the hot path) |
| **CLI tool** | · ctor injection + command registry at the root |
| **System script** | · ctor injection, or nothing — call the dependency directly |
| **Evaluation harness** | · ctor injection at the root |
| **Library** | · ctor injection — accept dependencies, never construct; the caller wires |

`svcs` slots in wherever a **runtime locator** (resolve-by-type) is wanted over declarative wiring; `dependency-injector` only when its provider catalogue is the point. Read alongside `application_map.md` (same categories, macro-structure intensity).

## What to reach for, and what not

| Tool | Async | Backend | Reach for it when | License · maturity |
|---|---|---|---|---|
| **constructor injection** | same | builtin | **default** — pass ports as args, wire at the root | stdlib |
| framework-native `Depends` | async | — | inside a FastAPI app: request-scoped, integrated | FastAPI-native, Apache-2.0 |
| **`dishka`** | **async-native** | pure-py, light | standalone graph with real scopes (app/request/custom); finalization via generator (RAII) | Apache-2.0, active (reagento) |
| `svcs` | async | pure-py | service-*locator*: resolve by type at runtime + cleanup; pragmatic over declarative | MIT, ~5.6M/mo (Hynek) |
| `dependency-injector` | async (`AsyncResource`) | **Cython** | you need its provider zoo (Factory/Singleton/Configuration/Selector) and accept a global-ish container | BSD-3, v4.49.1 (2026-06-18), ~8.3M/mo |
| `lagom` · `wireup` · `that-depends` | async | pure-py | type-based autowiring, smaller surface | MIT — smaller ecosystems |

**Decision:** ctor injection → `Depends` (in an API) → `dishka` (async, scoped, standalone) → `svcs` (runtime locator) → `dependency-injector` (provider zoo only).

**Why dishka over dependency-injector when you do reach for a container:** native asyncio, first-class scopes with generator-based finalization (`dependency-injector` has no real async scope cleanup and leans on an implicit global container, which fouls concurrent tests), and ~20× faster in its own benchmark. `dependency-injector` wins only if you specifically want its declarative provider catalogue.

**Never:**
- fetch a global singleton via `import` deep in the core — that is a hidden hard dependency wearing a locator costume.
- pass the container itself around as a god-object; inject the *dependency*, not the resolver.
- run two DI mechanisms at once (a container fighting FastAPI `Depends`).
- read config at point of use — parse `pydantic-settings` once at the boundary, inject the value.

## Scopes — async (first) · sync

| Concern | Async (first) | Sync |
|---|---|---|
| singleton (process-wide) | module-level object built at root | same |
| request/session scope | `dishka` scope · FastAPI `Depends` | `dishka` sync container |
| generator finalization (RAII) | `async def provider() -> AsyncIterator[T]` | `def provider() -> Iterator[T]` → `lang-py-lifecycle` |
| runtime resolution by type | `svcs` (async `aget`) | `svcs` (`get`) |
| autowiring by annotation | `dishka` · `lagom` | `dependency-injector` · `lagom` |

## Config

`pydantic-settings` only — validated once, injected. Never `os.environ` / `python-dotenv` in the core. One `Settings` singleton per package, imported `as st`. Modular composition (multi-inheritance of `BaseSettings`) belongs to project layout → `proj-py-layout`.
