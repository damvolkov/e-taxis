# problem catalog — need → algorithm → skill

Skiena-style lookup. Read the **Need** and the **Signal** (the code smell or the words a user would say), take the **Algorithm**, note its **Complexity**, load the **Skill**. Skill column: `core` = `algo-py-core`, `graphs` = `algo-py-graphs`, `scale` = `algo-py-scale`, `numeric` = `algo-py-numeric`, `optim` = `algo-py-optim`.

| Need | Signal | Algorithm | Complexity | Skill |
|---|---|---|---|---|
| Remove duplicates keeping order | "unique", `if x not in list` | `dict.fromkeys` / seen-set | O(n) | core |
| Count occurrences | manual counter in a loop | `Counter` / hash map | O(n) | core |
| Cross two collections by key | nested loops | hash join (dict of one side) | O(n+m) | core |
| Top-k of n elements | `sorted(...)[:k]` | heap (`nlargest`) / `argpartition` | O(n log k) / O(n) | core |
| Search / insert in ordered data | linear scan | binary search (`bisect`) | O(log n) | core |
| Merge k sorted sequences | concat then re-sort | k-way merge (heap) | O(N log k) | core |
| Exact median / percentile | sort everything | quickselect / `partition` | O(n) avg | core |
| Repeated range sum / query | re-sum each time | prefix sums | O(1) query | core |
| Subarray/window meeting a condition | double loop | two-pointers / sliding window | O(n) | core |
| Recursion with repeated subproblems | exponential recursion | DP (memo or tabulation) | state-dependent | core |
| Explore combinations under constraints | generate-all then filter | backtracking with pruning | bounded exponential | core |
| Provably optimal local choice | sort + pick | greedy (validate the property) | O(n log n) | core |
| Order tasks by dependency | "before", "requires" | toposort (Kahn) | O(V+E) | graphs |
| Run a DAG level by level in parallel | task pipeline | incremental toposort (ready set) | O(V+E) | graphs |
| Detect circular dependencies | "cycle", "circular import" | DFS with colors / Kahn | O(V+E) | graphs |
| Shortest path, unweighted | "fewest hops" | BFS | O(V+E) | graphs |
| Shortest path, weights ≥ 0 | costs, latencies | Dijkstra (binary heap) | O((V+E) log V) | graphs |
| Path with spatial heuristic | maps, grids | A* | ≤ Dijkstra in practice | graphs |
| Negative weights | credits/debits | Bellman-Ford | O(VE) | graphs |
| Group connected elements / merge groups | "same group", entity resolution | union-find (DSU) | ~O(α(n)) per op | graphs |
| Strongly connected components | mutual cycles | Tarjan / Kosaraju | O(V+E) | graphs |
| Connect everything at minimum cost | network, hierarchical clustering | MST (Kruskal/Prim) | O(E log V) | graphs |
| One-to-one assignment / capacity | matching, max flow | bipartite matching / max-flow | polynomial | graphs |
| Queries over hierarchies | common ancestor, subtree | LCA / Euler tour | O(log n) query | graphs |
| Process a file > RAM | "huge log", OOM | streaming by chunks / lazy scan | O(n) time, O(chunk) memory | scale |
| Sort data > RAM | sort that won't fit | external merge sort | O(n log n) with I/O | scale |
| Uniform sample of a stream | unknown length | reservoir sampling | O(n), O(k) memory | scale |
| Metrics over a time window | "last 5 min" | sliding window (deque) / incremental aggregation | O(1) amortized | scale |
| Count uniques at scale | millions of ids | HyperLogLog | O(1) memory, ~1–2% error | scale |
| "Have I seen this before?" at scale | huge set | Bloom / Cuckoo filter | O(k), false positives | scale |
| Most frequent items in a stream | heavy hitters | Count-Min + heap / Misra-Gries | sublinear | scale |
| Quantiles in a stream | p95/p99 latency | t-digest / KLL | sublinear | scale |
| Near-duplicate documents | dedup at scale | MinHash + LSH | ~O(n) | scale |
| Match many patterns at once | keyword list | Aho-Corasick | O(text + matches) | scale |
| String similarity | "similar", typos | edit distance / fuzzy (Jaro, token ratio) | O(nm) per pair | scale |
| Differences between versions | diff | Myers diff | O((n+m)D) | scale |
| Parallelize a data transform | "more cores" | partitioning + map-reduce | data-dependent | scale |
| Sum many floats accurately | rounding error | `math.fsum` (Kahan/Shewchuk) | O(n) | numeric |
| Money / decimal precision | cents | `Decimal` with fixed context | O(n) | numeric |
| Mass aggregations / array ops | numeric loop | vectorization (SIMD via NumPy/Polars) | O(n), low constant | numeric |
| Mostly-empty matrices | memory explodes | sparse formats (CSR/CSC) | O(nnz) | numeric |
| Streaming mean/variance | online stats | Welford | O(1) per item | numeric |
| Schedule non-overlapping intervals | bookings | interval scheduling (greedy by end) | O(n log n) | optim |
| Fill containers / knapsack | capacity | knapsack (DP) / bin packing (heuristics) | pseudo-poly / approx | optim |
| Optimal plan under complex constraints | shifts, routes, assignments | CP-SAT / MIP | NP-hard, solver with time limit | optim |
| Optimize a continuous function | parameter fitting | numeric optimization (gradient, simplex) | problem-dependent | optim |
