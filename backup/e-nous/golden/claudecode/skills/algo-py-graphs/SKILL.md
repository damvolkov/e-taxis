---
name: algo-py-graphs
description: "Python: relations, dependencies and hierarchies — BFS/DFS, toposort, DAG execution, cycles, shortest paths, union-find, SCC, MST. Use when modeling dependencies, task DAGs, paths or connectivity."
metadata:
  family: design
---

# algo-py-graphs

Anything relational: who depends on whom, what connects to what, the shortest way through. Owns graphs, trees and hierarchies. Not here: knowledge graphs for retrieval and GNNs (`ml`), pure recursion mechanics (`para-py-iteration`), constrained assignment as optimization (`algo-py-optim`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Model as adjacency, index by integers.** `dict[node, list/set]` for clarity; contiguous integer ids (not heavy Python objects) once it is large or headed for `rustworkx`/`scipy.sparse`. → `references/lib.md`
2. **BFS and DFS are iterative.** BFS with a `deque` (never `list.pop(0)`); DFS with an explicit stack. Python has no TCO — recursive DFS overflows on real graphs. → `para-py-iteration`
3. **Order dependencies with `graphlib`.** `TopologicalSorter` for a static order; `prepare`/`get_ready`/`done` to run a DAG level by level, one `asyncio.TaskGroup` per wave. Detect the cycle first — toposort on a cyclic graph raises. → `references/algorithms.md`
4. **Shortest path by weight class.** Unweighted → BFS; weights ≥ 0 → Dijkstra (`heapq` + lazy deletion, no re-sort); with a spatial heuristic → A*; negative weights → Bellman-Ford. Choose and delegate; never implement an SSSP paper (Duan 2025 is theory, not practice).
5. **Connectivity and merges are union-find.** DSU with path compression + union by rank — ~O(α(n)) per op — for connected groups, entity resolution, Kruskal's MST.
6. **SCC, MST, flow, matching → a library.** Prefer `rustworkx`/`scipy.csgraph` over hand-rolling; keep only Tarjan (iterative) and DSU as short in-house code. → `references/algorithms.md`
7. **Never `networkx` on the hot path at scale.** It is the prototyping oracle; production scale is `rustworkx` (Rust, integer-indexed) or `scipy.sparse.csgraph`. → `references/lib.md`

## Sample

```python
import asyncio
from graphlib import TopologicalSorter

async def run_dag(deps: dict[str, set[str]], run) -> None:
    """Execute a task DAG wave by wave; tasks with met dependencies run concurrently."""
    ts = TopologicalSorter(deps)
    ts.prepare()                                  # raises CycleError if the graph is cyclic
    while ts.is_active():
        ready = tuple(ts.get_ready())             # a whole ready wave
        async with asyncio.TaskGroup() as tg:     # structured concurrency, no orphan tasks
            for node in ready:
                tg.create_task(run(node))
        ts.done(*ready)
```

`graphlib` owns the ordering; `TaskGroup` owns the concurrency. Cycle detection is `prepare()`, not an afterthought.

## References

- `references/modeling.md` — adjacency vs sparse matrix, integer indexing, when to leave pure Python
- `references/algorithms.md` — cards: BFS/DFS, toposort, cycles, Dijkstra/A*/Bellman-Ford, union-find, SCC, MST, LCA
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the chapters this domain leans on
- `references/lib.md` — the stack: `graphlib`, `rustworkx`, `scipy.csgraph`, `networkx`, offload
