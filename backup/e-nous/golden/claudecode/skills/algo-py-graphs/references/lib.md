# lib — the graph stack

What to reach for on graphs. Reach order: **builtin `graphlib` (ordering) → `rustworkx` (heavy, Rust) → `scipy.sparse.csgraph` (matrix-shaped)**. Graphs are CPU-bound; offload heavy calls. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The graph stack × the nine software categories.

| Category | Graph stack |
|---|---|
| **API service** | `graphlib` for request/task dependencies; `rustworkx` if graph queries are core |
| **Async worker** | `graphlib.TopologicalSorter` + `asyncio.TaskGroup` — the DAG scheduler |
| **ML pipeline** | `rustworkx` for pipeline DAGs; `scipy.csgraph` for matrix-shaped graphs |
| **Agent system** | `graphlib` for tool/step DAGs; `rustworkx` for larger reasoning graphs |
| **Voice runtime** | `graphlib` — tiny, static processing graph |
| **CLI tool** | `graphlib` (builtin) |
| **System script** | `graphlib` — dependency resolution, build order |
| **Evaluation harness** | `rustworkx`; `networkx` as the correctness oracle in tests |
| **Library** | `graphlib` only, unless graphs are the library's purpose |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `graphlib` | `TopologicalSorter` — toposort, DAG waves, cycle detection | any dependency ordering | stdlib |
| `rustworkx` | Rust engine, integer-indexed; paths, components, MST, matching, SCC | performance or large graphs; hot path | Apache-2.0, Rust (Qiskit) |
| `scipy.sparse.csgraph` | graph algorithms over sparse matrices | the graph is naturally a sparse matrix | BSD, C |

Union-find without hand-rolling → `scipy.cluster.hierarchy.DisjointSet`. `networkx` is the prototyping/test oracle, never the production hot path. `igraph`/`graph-tool` only for an algorithm `rustworkx` lacks.

**Never:** recursive DFS at scale · BFS with `list.pop(0)` · Dijkstra without lazy deletion · heavy Python objects as nodes in a million-edge graph · `networkx` on a hot path · toposort without cycle detection · a DAG orchestrated with recursion instead of `graphlib`.

## Offload

Heavy algorithm off the loop: `asyncio.to_thread(rustworkx.…)`. DAG execution: `graphlib` + `asyncio.TaskGroup`. Details → `conc-py-async`.

## Testing

`pytest` (+ `anyio`), `hypothesis` on random graphs checking invariants against `networkx` as oracle (distances, components), `pytest-benchmark` for hot paths.
