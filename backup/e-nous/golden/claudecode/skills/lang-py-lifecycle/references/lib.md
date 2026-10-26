# lib — the resource & error stack

Criterion: **builtin > Rust-backed > C/Cython > pure Python**. Async first, sync the alternative where it applies.

Most of this domain is builtin: `contextlib`, `asyncio`, `weakref` and `ExceptionGroup` are the stack. Libraries enter only for retries, pools, servers, validation and tooling.

**Never:** `__del__` for cleanup · a bare `except`/`except BaseException` · swallowing `CancelledError` · `create_task` without an owner (→ `conc-py-async`) · `time.sleep`/blocking IO on the loop.

## By software category

The scope/cleanup primitives (`ExitStack`, `TaskGroup`, `suppress`, `ExceptionGroup`) are builtin and universal — they do not change by category. What changes is *which resource* each category owns, and therefore which pooled/retry/server library sits behind the same `with`. `⟳` = async default.

| Category | Resource libraries behind the scope |
|---|---|
| **API service** | `wreq.Client` ⟳ pool · server lifespan (`granian`/`uvicorn` + `asynccontextmanager`) · `structlog` |
| **Async worker** | `TaskGroup` ⟳ · `tenacity`/`stamina` retries · `Semaphore` · DB pool (`asyncpg`) |
| **ML pipeline** | `asyncio.to_thread` for blocking model calls · `TaskGroup` ⟳ · `ExitStack` for handles |
| **Agent system** | `AsyncExitStack` ⟳ (many nested clients) · `asyncio.timeout`/`shield` |
| **Voice runtime** | `aclosing` ⟳ on streams · `to_thread` for device IO · `anyio.CancelScope` |
| **CLI tool** | `ExitStack` · `subprocess.run` · `closing` (builtin, sync) |
| **System script** | `ExitStack` · `subprocess` · `suppress` (builtin, sync) |
| **Evaluation harness** | `TaskGroup` ⟳ for parallel runs · `ExitStack` for fixtures |
| **Library** | `contextlib` primitives only (force no dep) · `weakref.finalize` fallback |

The invariant: **the scope tool is builtin everywhere; only the pooled resource, retry and server libraries differ by category.**

## Stack — async (first) · sync

`wreq` traps when scoping a client: timeouts are `datetime.timedelta` (an int raises at construction), redirects are **off** unless `redirect=Policy.limited()`, `.json()`/`.text()` must be awaited, and `status` is a `StatusCode`. It exposes no transport, so there is no in-process fake to enter the scope (→ `test-py-tdd`).

The fixed summary: what to reach for, by concern. Builtin / Rust-backed always first.

| Concern | Async (first) | Sync |
|---|---|---|
| scopes & cleanup | `AsyncExitStack` · `asynccontextmanager` · `aclosing` (builtin) | `ExitStack` · `contextmanager` · `closing` · `suppress` (builtin) |
| structured concurrency | `asyncio.TaskGroup` (builtin); `anyio` for multi-backend → `conc-py-async` | `concurrent.futures` pools in a `with` (builtin) |
| timeouts / cancellation | `asyncio.timeout` · `asyncio.shield` (builtin); `anyio.CancelScope` | per-API timeouts: `subprocess.run(timeout=)`, `queue.get(timeout=)` |
| event loop | `uvloop` (libuv/Cython) · `rloop` (Rust, experimental) | — |
| aggregate errors | `ExceptionGroup` / `except*` (builtin, 3.11+) | same |
| retries | `tenacity` · `stamina` (async-capable) | `tenacity` · `stamina` |
| finalization fallback | `weakref.finalize` (builtin) | `weakref.finalize` (builtin) |
| locks / limits | `asyncio.Lock` · `Semaphore` · `BoundedSemaphore` (builtin) | `threading.Lock` · `RLock` · `BoundedSemaphore` (builtin) |
| file IO | `anyio.Path` · `asyncio.to_thread` (disk IO is not truly async) | `pathlib` · `open` · `mmap` (builtin) |
| HTTP (pooled) | `wreq.Client` in `async with` · `aiohttp.ClientSession` | `wreq.blocking.Client` in `with` |
| DB pools | `asyncpg` (Cython) · `psycopg[pool].AsyncConnectionPool` · SQLAlchemy 2 async | `psycopg[pool].ConnectionPool` · SQLAlchemy 2 |
| subprocess | `asyncio.create_subprocess_exec` (builtin) | `subprocess.run` (builtin) |
| server lifespan | `granian` (Rust ASGI) · `uvicorn` + lifespan `asynccontextmanager` | `granian` (WSGI) |
| validation errors | `pydantic` v2 (Rust core) · `msgspec` (C) | same |
| error logging | `structlog` | `logging` (builtin) · `structlog` |
| linting | `ruff`: `ASYNC` `BLE` `TRY` `B012` `SIM105` `RUF006` | `ruff`: `BLE` `TRY` `B012` `SIM105` `SIM115` |
| typing | `ty` (Rust) · `pyright` · `mypy` | same |
| testing | `pytest` + `anyio`/`pytest-asyncio` · `pytest.RaisesGroup` · `pytest-stress` (leaks only repeat runs catch, → `test-py-tdd`) | `pytest.raises` · `-X dev` · `-W error::ResourceWarning` |
