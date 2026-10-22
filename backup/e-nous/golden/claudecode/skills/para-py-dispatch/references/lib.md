# lib — the dispatch stack

The single authority on what to import for dispatch, and what never to. Most dispatch is builtin — a `Final` frozen mapping or `match`. A library enters only for **type-driven multiple dispatch**, where the argument types *are* the condition and a hand-written `isinstance` chain would be the alternative.

The mechanism is chosen by **what varies** (a closed value set, argument types, an open plugin set), **not by software category** — so the ladder is identical across every kind of app. The only thing category changes is whether the handlers are coroutines, and the libraries below are all async-friendly. Order of reach: **builtin mapping / `match` → `functools.singledispatch` → `ovld` → `plum-dispatch`.** Dates from the September 2026 survey; re-verify → `flow-gen-research`.

## Libraries — what to reach for, and what not

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| **frozen `Mapping` / `match`** | builtin value dispatch | a closed set of keys → handlers; O(1) | stdlib |
| `functools.singledispatch` | builtin type dispatch | single-argument, **sync only**, no dependency allowed | stdlib |
| **`ovld`** | multiple dispatch | several args, `Literal` types, coroutines — the default library | MIT |
| `plum-dispatch` | multiple dispatch | a signature `ovld` cannot express | MIT |
| registry + `__init_subclass__` | builtin open dispatch | handlers declare themselves; the dispatcher never changes → `registry.md` | stdlib |

## By software category

Category does not move the mechanism — it only sets whether handlers are async. The ladder is the same everywhere; pick by what varies, then reach for the async-capable library when the handlers are coroutines.

| Category group | Typical |
|---|---|
| **API · Async worker · Agent · ML · Voice** (async handlers) | frozen `Mapping` (builtin) → `ovld` for type/`Literal` dispatch over coroutines |
| **CLI · System script · Evaluation · Library** (often sync) | frozen `Mapping` / `match` (builtin) → `functools.singledispatch` or `ovld` |

## Stack — async · sync

| What varies | Async | Sync |
|---|---|---|
| value from a closed set | frozen `Mapping[Enum, Handler]` (builtin) | same |
| single argument type | `ovld` | `functools.singledispatch` · `ovld` |
| several arg types / `Literal` / coroutine | `ovld` · `plum-dispatch` | `ovld` · `plum-dispatch` |
| nested structure, mixed types | `match` with class patterns (builtin) | same |
| an open, extensible set | registry + `__init_subclass__` (builtin) | same |

**Never:** an `isinstance`/`if`-`elif` chain (that is hand-rolled multiple dispatch — use `ovld`) · `functools.singledispatch` on async functions (it cannot await — use `ovld`) · raw string keys in the mapping (use a `StrEnum`) · a mutable module-level dispatch table (`Final` + `MappingProxyType`).
