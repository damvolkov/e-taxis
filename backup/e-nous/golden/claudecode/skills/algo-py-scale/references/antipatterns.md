# antipatterns — scale

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| `read()` / `readlines()` a large file | loads the whole file into RAM | iterate lines or fixed-size chunks |
| eager `pandas` over > RAM | OOM | `polars` streaming / `duckdb` out-of-core |
| `set` of millions of strings for membership | O(n) memory | Bloom filter (`rbloom`) — O(bits) |
| exact distinct count with a `set` | O(n) memory | HyperLogLog — O(1) memory, ~1% error |
| all-pairs O(n²) similarity | quadratic blow-up | MinHash + LSH — ~O(n) |
| loop of `re.search` per keyword | O(patterns × text) | Aho-Corasick — O(text + matches) |
| hand-rolled Levenshtein in Python | interpreter-bound | `rapidfuzz` (C++) |
| `difflib` on enormous texts unbounded | quadratic memory | bound the input or use an external diff |
| sort > RAM with `sorted()` | OOM | external merge sort / `polars` sort with spill |
| pickle large data across processes | serialization dominates | partition at the source, ship references |
| CSV for intermediate data | re-parse, untyped, slow | Parquet/Arrow with pushdown |
| recompute a whole window per step | O(n·w) | incremental aggregation / `deque(maxlen)` |
| treating a Bloom/Count-Min hit as exact | wrong logic | respect the "maybe" / overestimate semantics |
