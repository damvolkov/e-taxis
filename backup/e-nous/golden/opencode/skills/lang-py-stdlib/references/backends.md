# backends — embedded storage and config, before a service

Reach an in-process backend before standing up a server. The stdlib carries most of them; structured config is the one place the house leads with a Rust engine.

## Structured config — `e-serde` first

`e-serde` (import `eserde`) is the house loader for any structured config: native **Rust** codecs for `json / jsonc / yaml / toml / ini / cfg / conf`, one API, sync and async twins. A `Path` autodetects the format from its suffix; `bytes`/`str` name it via `Format`.

```python
import eserde
cfg = eserde.load(path)                       # plain dict tree; format from the suffix
cfg = await eserde.aload(path)                # the async twin — no offload needed
srv = eserde.loads(raw, format=Format.JSON, type=Server)   # decode straight into a frozen msgspec model
```

- It is the loader/parser, not the modeller: `type=` targets a `msgspec.Struct` you defined in `lang-py-datamodel` — the model stays there, `e-serde` fills it.
- It replaces reaching for `json`/`orjson`/`msgspec.json`/`tomllib`/`configparser` *as loaders*; one dependency covers every config format.
- Stdlib fallback for a **zero-dependency cold path**: `tomllib` (read-only TOML, 3.11+), `json`, `configparser` — when adding a dep is not worth it.

## Local storage — `sqlite3`, `dbm`, `shelve`

- **`sqlite3`** — a real transactional SQL database in one file: local structured storage, caches that must survive a restart, embedded analytics. Reach for it before a Postgres for anything single-node and modest. Analytical/columnar at scale → `algo-py-scale` (duckdb).
- **`dbm`** / **`shelve`** — a persistent key→bytes (or key→pickled-object) file when SQL is overkill.

## Tabular text — `csv`

`csv.reader`/`DictReader` for row text; correct quoting and dialects out of the box. Mass/columnar CSV → `polars` (`algo-py-scale`); `csv` is for modest, streaming, dependency-free row work.

## Bytes at rest — `compression`

`gzip`, `bz2`, `lzma`, and **`compression.zstd`** (Zstandard, stdlib since 3.14) for compressing stored/transferred bytes; `zstd` is the modern default — fast and dense. Pair with the atomic-write pattern for compressed artifacts.
