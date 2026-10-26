# antipatterns — graphs

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| recursive DFS on large graphs | stack overflow | explicit stack, iterative |
| BFS with `list.pop(0)` | O(n) per dequeue → O(n²) | `collections.deque` + `popleft` |
| Dijkstra with a re-sort each step | O(V² log V) | binary heap + lazy deletion |
| Dijkstra without the stale-entry skip | pushes never pruned, blow-up | skip when `d > dist[u]` |
| Dijkstra on negative weights | wrong distances | Bellman-Ford |
| recompute reachability per query | O(q·(V+E)) | precompute components / transitive closure once |
| heavy Python objects as nodes at scale | dict-hash + pointer chase per edge | integer-indexed adjacency; `rustworkx` |
| `networkx` on a production hot path | 10–100× slower than Rust | `rustworkx` / `scipy.csgraph` |
| toposort without cycle detection | silent wrong order or crash | `graphlib.prepare()` catches `CycleError` first |
| orchestrate a DAG with recursion | re-invents scheduling, no concurrency | `graphlib` waves + `asyncio.TaskGroup` |
| hand-rolled SCC/MST/flow | subtle bugs, slower | `rustworkx` / `scipy.csgraph` |
| union-find without path compression / rank | O(n) per find | halving + union by rank → ~O(α(n)) |
