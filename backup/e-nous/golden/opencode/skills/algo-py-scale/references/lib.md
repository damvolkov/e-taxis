# lib — the scale stack

What to reach for on data that is large, streaming or approximate, and text at scale. Reach order: **builtins (`heapq.merge`, generators) → `polars`/`duckdb` (out-of-core) → the sketch/string specialist**. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The scale stack × the nine software categories.

| Category | Scale stack |
|---|---|
| **API service** | streaming async generators; `datasketches` for live cardinality/quantiles |
| **Async worker** | `polars` streaming / `duckdb` for batch; `anyio` streams for backpressure |
| **ML pipeline** | `polars` lazy; `datasketch` MinHash/LSH for dedup |
| **Agent system** | `datasketches` for frequency budgets; `rapidfuzz` for fuzzy name matching |
| **Voice runtime** | `deque` sliding windows, incremental aggregation on the audio path |
| **CLI tool** | `duckdb` for ad-hoc out-of-core; builtin `heapq.merge` for external sort |
| **System script** | generators + `mmap` + `heapq.merge`; `polars` scan for large logs |
| **Evaluation harness** | `polars` for batch metrics; `datasketches` KLL for p95/p99; `rapidfuzz` for scoring |
| **Library** | builtins (`heapq.merge`, generators); a sketch dep only if that is its job |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `polars` | Rust dataframe, streaming engine, spills to disk | out-of-core tabular; `collect_async()` | MIT, Rust (out-of-core spill since 1.42, 2026) |
| `datasketches` | Apache sketches: HLL, KLL, Frequent Items | cardinality, quantiles, heavy hitters with proven bounds | Apache-2.0, C++ |
| `datasketch` | MinHash, LSH | near-duplicate / Jaccard similarity at scale | MIT, Python + NumPy |
| `rapidfuzz` | edit distance, Jaro-Winkler, token ratios (`process.cdist`) | fuzzy matching / string similarity | MIT, C++ |
| `ahocorasick-rs` | multi-pattern search (Rust `aho-corasick`) | match many keywords in one pass | MIT, G-Research |

SQL interface to out-of-core → `duckdb`; Bloom membership → `rbloom`; line diff → `difflib` (stdlib). Columnar IO uses `pyarrow`/Parquet under `polars`.

**Never:** `read()`/`readlines()` a huge file · eager `pandas` over > RAM · a `set` of millions of strings when a sketch fits · all-pairs O(n²) instead of LSH · a loop of `re.search` instead of Aho-Corasick · pickle large data across processes instead of partitioning at the source · CSV for intermediate data instead of Parquet.

## Streaming & offload

Lazy scan: `polars` `scan_*` + `collect_async()`. Streaming IO: `anyio` streams / async generators + `aclosing`. Sketch/fuzzy/multi-pattern (CPU): `asyncio.to_thread` (`rapidfuzz` `workers=`). Data parallelism: `anyio.to_process`. Backpressure → `para-py-iteration`; offload → `conc-py-async`.

## Testing

`pytest` (+ `anyio`), `hypothesis` comparing a sketch against the exact structure within tolerance (HLL vs `len(set)`), `pytest-benchmark` for throughput.
