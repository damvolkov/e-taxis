# lib — the reach ladder and upgrade map

The stdlib is the default; this is when and to what you upgrade. Reach order at every call site: **stdlib primitive → Rust/C-backed engine (hot path) → async twin (touches the loop)**. Most upgrade targets are owned by another skill's `lib.md`; here is the map and the one house primary, `e-serde`. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The stdlib systems surface × the nine categories — what each leans on beyond the primitive.

| Category | Stdlib + upgrade |
|---|---|
| **API service** | `pathlib`/`os`; config via `e-serde`; `sqlite3` for local state |
| **Async worker** | `e-serde` `aload` for config; `sqlite3`; async file IO → `para-py-iteration` |
| **ML pipeline** | `mmap`/`memoryview` for large reads; `csv`→`polars`; `e-serde` config |
| **Agent system** | `e-serde` for config/MCP files; `uuid7` ids; `secrets` tokens |
| **Voice runtime** | `struct`/`mmap` on frames/buffers; `time.perf_counter` budgets |
| **CLI tool** | `pathlib`, `tomllib`/`e-serde` config, `argparse`/typer |
| **System script** | `pathlib`, `shutil`, `subprocess`, atomic writes |
| **Evaluation harness** | `sqlite3`/`csv` for runs; `perf_counter`; `secrets` seeds off |
| **Library** | stdlib only in the public path — force no dependency on the consumer |

## The upgrade map

| Stdlib | Upgrade to | When | Owner |
|---|---|---|---|
| `json`·`tomllib`·`configparser` (as a **loader**) | **`e-serde`** | any structured config (json/jsonc/yaml/toml/ini), one API, async | this skill |
| defining/validating a model | `msgspec`·`pydantic` | the data *model* (not loading) | `lang-py-datamodel` |
| `hashlib` (non-crypto) | `xxhash`·`blake3` | fast hashing on a hot path | `algo-py-core` |
| `csv` (mass) | `polars` | columnar/large tabular | `algo-py-scale` |
| `sqlite3` (analytical) | `duckdb` | out-of-core/columnar queries | `algo-py-scale` |
| blocking file IO | `aiofile` | throughput/async disk | `para-py-iteration` |
| `subprocess` | `asyncio.create_subprocess_*` | off the event loop | `conc-py-async` |
| `urllib` | **`wreq`** | real HTTP client | `api` |

**`wreq`** (import `wreq`): the house HTTP client — Rust (`wreq` crate, BoringSSL, abi3 wheel, py≥3.11, no runtime deps). 0.12.3 · 2026-09-27 · 1.4k★ · 186k dl/mo (`0x676e67/wreq-python`, Apache-2.0): async `Client` + `wreq.blocking.Client`, timeouts as `datetime.timedelta`, **redirects off unless `redirect=Policy.limited()`**, `status` is a `StatusCode` (`as_int()`/`is_success()`) not an int, `.json()`/`.text()` are awaitables, `.stream()` yields bytes; TLS/JA3/JA4/HTTP/2 fingerprint control with 100+ browser emulations, WebSocket, rotating proxies. No transport injection → nothing to mock (→ `test-py-tdd`).

**`httpxr`** (import `httpxr as httpx`): the httpx-compatibility path — 1:1 Rust port of the httpx API (0.30.24 · MIT, `bmsuisse/httpxr`): `AsyncClient`, `follow_redirects`, `MockTransport`, `ASGITransport`. Young: 3★, pushed 2026-04-02 → verify before pinning (`flow-gen-research`). **`httpx2`** (import `httpx2 as httpx`): Pydantic's pure-Python continuation of the deprecated `encode/httpx` (0.28.1); 2.13.1 · 2026-09-27, anyio-backed, the maintained fallback and the target of ecosystem extras (`hishel[httpx2]`). Neither exposes a module named `httpx`: the alias is yours to write, and any third party that does `import httpx` still drags the deprecated one.

**`e-serde`** (import `eserde`): universal structured-config loader — native Rust codecs + a `msgspec` backend, `loads/dumps/load/dump` with async twins, decode into a frozen `msgspec` model via `type=`. MIT, Eager stack. It is the loader, never the modeller — msgspec-as-datamodel stays in `lang-py-datamodel`.

**Never:** a dependency where a stdlib primitive suffices · `os.path` over `pathlib` · a naive datetime across a boundary · `random` for a secret · truncate-in-place for a durable write · `json`/`orjson` hand-wired as a config loader when `e-serde` covers every format.

## Testing

Assert the primitive's guarantee: an atomic write leaves the old file intact on a simulated mid-write crash; a `monotonic` duration never goes negative; `e-serde` round-trips each format; a `secrets` token is high-entropy. `tmp_path`/`monkeypatch` (builtin) isolate the filesystem → `test-py-tdd`.
