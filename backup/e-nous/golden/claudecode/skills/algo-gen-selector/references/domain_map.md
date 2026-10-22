# domain map — ownership across the algo skills

Every algorithmic domain has **one owner skill**. Neighbours only reference it; they never re-teach it. When a need spans two domains, the owner is the one that drives the complexity; the other is referenced.

| Domain | Core algorithms | Typical need | Owner |
|---|---|---|---|
| Search & sort | stable sort with `key`, binary search, heaps, partial selection (top-k, quickselect), k-way merge | order, rank, search in ordered data | `algo-py-core` |
| Hashing & sets | dict/set, dedup, hash join, counting, grouping | group, deduplicate, cross | `algo-py-core` |
| Design paradigms | divide & conquer, backtracking with pruning, DP (memo → tabulation → space reduction), greedy, two-pointers, prefix sums | decomposition, small/medium combinatorial optimization | `algo-py-core` |
| Graphs | BFS/DFS (iterative), toposort, Dijkstra/A*/Bellman-Ford, union-find, SCC, MST, cycles, flow & matching | dependencies, task DAGs, paths, reachability, connectivity clustering | `algo-py-graphs` |
| Trees & hierarchies | traversals, LCA, interval/segment trees, structural tries | hierarchies, ranges, prefixes | `algo-py-graphs` (text tries → `algo-py-scale`) |
| Streaming / bounded memory | sliding windows, reservoir sampling, external sort/merge, chunked processing | data in flight or > RAM | `algo-py-scale` |
| Probabilistic / approximate | Bloom/Cuckoo, HyperLogLog, Count-Min, t-digest/KLL, MinHash/LSH | cardinality, frequency, quantiles, similarity at scale | `algo-py-scale` |
| Strings & sequences | Aho-Corasick, rolling hash, edit distance, diff (Myers), fuzzy matching | multi-pattern match, comparison, text dedup | `algo-py-scale` |
| Data parallelism | partitioning, map-reduce, shuffle, distributed joins | spread compute across cores/processes | `algo-py-scale` (async orchestration → `conc-py-async`) |
| Numeric computation | vectorization, stability (fsum, Kahan/Welford), Decimal/Fraction, sparse algebra, aggregations | statistics, finance, mass metrics | `algo-py-numeric` |
| Scheduling & optimization | interval scheduling, knapsack, bin packing, LP/MIP, constraint programming (CP-SAT), continuous optimization | plan tasks, assign resources, best plan under constraints | `algo-py-optim` |

## Size thresholds

Orientative — the size decides how much you may keep in pure Python.

| n | Reasonable approach |
|---|---|
| < 10³ | Clarity first; almost any algorithm serves |
| 10³–10⁶ | Complexity matters; builtins and the right data structure |
| 10⁶–10⁸ | Delegate to Rust/C (Polars, NumPy, rustworkx); no Python loops on the hot path |
| > 10⁸ or > RAM | Streaming, out-of-core, sketches, partitioning |

## Out of scope of Layer 2

These are owned by other families, not by `algo-*`: RAG, embeddings and vector retrieval indexes (`ml`), ML training (`ml`), cryptography (`sec`), low-level compression, and distributed infrastructure — queues, clusters, schedulers (`sys` · `sched` · `conc`).
