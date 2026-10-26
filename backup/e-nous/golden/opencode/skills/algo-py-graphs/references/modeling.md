# modeling — representing a graph

The representation decides the constant factor. Choose it before the algorithm.

## Representations

| Representation | Shape | Good for | Cost |
|---|---|---|---|
| Adjacency dict | `dict[node, set/list[node]]` | clarity, sparse graphs, dynamic edges | O(V+E) memory; Python-object overhead |
| Adjacency + integer ids | `list[list[int]]`, nodes mapped to `0..V-1` | performance, feeding `rustworkx`/`scipy` | contiguous, cache-friendly |
| Sparse matrix | `scipy.sparse` CSR/CSC | matrix algorithms (paths, components, flow) | O(nnz); vectorized |
| Edge list | `list[tuple[u, v, w]]` or a `polars` frame | building/ingesting, MST (Kruskal) | needs conversion for traversal |

## Integer indexing

Heavy Python objects as nodes cost dict hashing and pointer chasing on every edge visit. For anything large or headed to a Rust/C engine: map nodes to contiguous integers once, run on the integer graph, map back at the boundary.

```python
index = {node: i for i, node in enumerate(nodes)}          # node → id, once
adj = [[] for _ in nodes]
for u, v in edges:
    adj[index[u]].append(index[v])                          # integer adjacency
```

## When to leave pure Python

- < 10⁴ nodes, one-shot: adjacency dict + iterative BFS/DFS is fine.
- 10⁴–10⁶ or repeated queries: integer-indexed adjacency; consider `rustworkx`.
- > 10⁶ edges, or matrix-shaped algorithms: `rustworkx` or `scipy.sparse.csgraph`, never a Python loop over edges.
- Trees / hierarchies: an explicit parent array or child lists; LCA via binary lifting or an Euler tour + sparse table when queries are many.
