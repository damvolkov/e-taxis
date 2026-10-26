---
name: algo-py-scale
description: "Python: large, streaming or approximate data and text at scale — external sort, sketches (HLL, Bloom, Count-Min), MinHash/LSH, Aho-Corasick. Use when data won't fit in RAM or exactness is too costly."
metadata:
  family: design
---

# algo-py-scale

When the data is too big, too fast, or exactness is not worth its price. Owns streaming and bounded memory, probabilistic/approximate structures, strings at scale, and data parallelism. Not here: embeddings and vector retrieval (`ml`), distributed infrastructure — queues, clusters (`sys`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Stream; never materialize what you can consume.** Lazy scan, process in chunks, apply backpressure. `read()`/`readlines()` of a large file is a bug. → `para-py-iteration` · `conc-py-async`
2. **Out-of-core over hand-rolled.** External merge sort via `heapq.merge` over sorted runs; columnar Parquet/Arrow with projection + predicate pushdown; `polars` streaming engine and `duckdb` spill to disk — reach for them before writing spill logic. → `references/lib.md`
3. **Approximate at scale, and name the error.** Cardinality → HyperLogLog; membership → Bloom/Cuckoo; heavy hitters → Count-Min/Misra-Gries; quantiles → t-digest/KLL. Use a sketch only where the error bound is acceptable, and state it. → `references/algorithms.md`
4. **Sample without knowing the length.** Reservoir sampling for a uniform sample of a stream; stratified when classes matter.
5. **Similarity is not all-pairs.** Near-duplicate detection is MinHash + LSH (~O(n)); comparing every pair is O(n²) and forbidden at scale.
6. **Text at scale has its own algorithms.** Many patterns at once → Aho-Corasick (not a loop of `re.search`); fuzzy/edit distance → `rapidfuzz`; version diff → Myers.
7. **Partition at the source.** Split by hash/range and map-reduce; let `polars`/`duckdb` own big joins; never pickle large data across processes. → `conc-py-async`

## Sample

```python
import random
from typing import Iterator

def reservoir(stream: Iterator[T], k: int) -> list[T]:
    """A uniform sample of k items from a stream of unknown length — O(n) time, O(k) memory."""
    sample: list[T] = []
    for i, item in enumerate(stream):
        if i < k:
            sample.append(item)
        elif (j := random.randint(0, i)) < k:   # keep with probability k/(i+1)
            sample[j] = item
    return sample
```

One pass, bounded memory, never holds the stream. The whole domain is this shape: consume once, keep little.

## References

- `references/streaming.md` — chunking, external merge sort, columnar IO, sliding windows, backpressure
- `references/algorithms.md` — cards: reservoir, HLL, Bloom/Cuckoo, Count-Min, t-digest/KLL, MinHash/LSH, Aho-Corasick, edit distance, Myers diff
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the chapters this domain leans on
- `references/lib.md` — the stack: `polars`/`duckdb`/`pyarrow`, `datasketches`/`datasketch`, `rapidfuzz`, `ahocorasick-rs`, offload
