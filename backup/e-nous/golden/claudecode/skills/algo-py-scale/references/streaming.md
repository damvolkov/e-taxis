# streaming — bounded memory over big data

Consume once, keep little. The mechanics of laziness and backpressure live in `para-py-iteration` and `conc-py-async`; this file is the scale-specific patterns.

## Chunking

Never `read()`/`readlines()` a large file. Iterate lines, or read fixed-size blocks, and process each chunk before the next.

```python
def chunks(path, size: int = 1 << 20):
    """Yield fixed-size byte blocks — memory is O(size), not O(file)."""
    with open(path, "rb") as f:
        while block := f.read(size):
            yield block
```

For tabular data, do not hand-roll: `polars.scan_csv/scan_parquet` + a lazy pipeline + `collect(engine="streaming")` spills to disk; `duckdb` runs SQL out-of-core.

## External merge sort

Sort data that won't fit: split into runs that fit in RAM, sort each, write sorted; then merge the runs with `heapq.merge` (lazy, O(k) memory).

```python
import heapq
def merge_runs(run_paths):
    """Merge pre-sorted files into one sorted stream, holding one line per run."""
    files = [open(p) for p in run_paths]
    try:
        yield from heapq.merge(*files)          # streaming k-way merge
    finally:
        for f in files: f.close()
```

Prefer `polars`/`duckdb` sort with spill when the data is tabular — they already do this, tuned.

## Columnar IO

- Parquet/Arrow over CSV for any intermediate data: typed, compressed, columnar.
- Push projection (only the columns) and predicates (only the rows) down to the scan — `polars`/`pyarrow` datasets read only what the query needs.
- Zero-copy interchange between Arrow-backed tools (`polars` ↔ `pyarrow` ↔ `duckdb`) avoids re-serialization.

## Sliding windows

Fixed-size or time windows: `collections.deque(maxlen=n)` for count windows; for time windows, evict from the left while the oldest is out of range. Aggregate incrementally (running sum/count, or a monotonic deque for a running max) — never recompute the whole window per step.

## Backpressure

A fast producer must not outrun a slow consumer. Bound the buffer: `anyio` memory object streams with a fixed buffer size, or `asyncio.Queue(maxsize=n)` — the producer blocks when full. Details → `conc-py-async`.
