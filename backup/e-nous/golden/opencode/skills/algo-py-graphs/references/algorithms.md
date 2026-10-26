# algorithms — graph cards

One card per algorithm. Pure-Python reference is iterative (Python has no TCO) and ≤25 lines. Delegate per `lib.md`.

### BFS — unweighted shortest path / reachability
- Solves: fewest-hop distance, reachable set, level order.
- Complexity: O(V+E); memory O(V).
```python
from collections import deque
def bfs(adj: dict[int, list[int]], src: int) -> dict[int, int]:
    """Hop distance from src to every reachable node."""
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()                       # deque, never list.pop(0)
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist
```
- Traps: `list.pop(0)` (O(n)); revisiting nodes (mark on enqueue, not dequeue).
- Tests: single node, disconnected target, cycle, self-loop.

### DFS — iterative
- Solves: reachability, discovery/finish order, backbone of SCC and cycle detection.
- Complexity: O(V+E).
- Pure Python: explicit `stack`; push children, mark visited on pop or push. Never recursive on large graphs.
- Traps: recursion overflow; not tracking the three colors (white/gray/black) when you need back-edge detection.
- Tests: chain (deep), wide fan-out, cycle, disconnected.

### Toposort — Kahn
- Solves: a linear order respecting dependencies; DAG scheduling.
- Preconditions: acyclic (a cycle → no order).
- Complexity: O(V+E).
- Pure Python: `graphlib.TopologicalSorter` — don't hand-roll; use `get_ready`/`done` for waves.
- Traps: running on a cyclic graph without catching `CycleError`; scheduling before verifying acyclicity.
- Tests: linear chain, diamond, disconnected components, cycle (must raise).

### Cycle detection
- Solves: circular dependencies / imports.
- Complexity: O(V+E).
- Pure Python: DFS with gray/black colors (a gray→gray edge is a back edge), or catch `graphlib.CycleError`.
- Traps: undirected vs directed confusion; treating a re-visited black node as a cycle.
- Tests: acyclic DAG, self-loop, two-node cycle, back edge deep in a chain.

### Dijkstra — non-negative weights
- Solves: shortest path with weights ≥ 0.
- Complexity: O((V+E) log V) with a binary heap.
```python
import heapq
def dijkstra(adj: dict[int, list[tuple[int, float]]], src: int) -> dict[int, float]:
    """Shortest distance from src; lazy deletion instead of decrease-key."""
    dist = {src: 0.0}
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):     # stale entry, skip — the lazy deletion
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
```
- Delegate to: `rustworkx.dijkstra_shortest_paths`, `scipy.sparse.csgraph.dijkstra` at scale.
- Traps: negative weights (wrong result — use Bellman-Ford); re-sorting instead of a heap; no lazy-deletion skip.
- Tests: single node, unreachable node, equal-weight ties, a graph where a greedy non-heap approach fails.

### A* — heuristic search
- Solves: shortest path with an admissible heuristic (grids, maps).
- Complexity: ≤ Dijkstra in practice; same worst case.
- Pure Python: Dijkstra with priority `g + h(node)`, `h` admissible (never overestimates).
- Traps: inadmissible heuristic (loses optimality); recomputing `h` expensively; heuristic not consistent.
- Tests: `h=0` reduces to Dijkstra; obstacle maze; heuristic tie-breaking.

### Bellman-Ford — negative weights
- Solves: shortest path with negative edges; detects negative cycles.
- Complexity: O(VE).
- Pure Python: relax all edges V-1 times; a further relaxation ⇒ a negative cycle.
- Traps: using it when Dijkstra suffices (slower); not reporting the negative cycle.
- Tests: negative edge but no negative cycle, negative cycle (must flag), disconnected.

### Union-find (DSU)
- Solves: connected groups, entity resolution, Kruskal's MST.
- Complexity: ~O(α(n)) per op with path compression + union by rank.
```python
def make_dsu(n: int):
    parent, rank = list(range(n)), [0] * n
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]     # path compression (halving)
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb: return
        if rank[ra] < rank[rb]: ra, rb = rb, ra
        parent[rb] = ra
        rank[ra] += rank[ra] == rank[rb]
    return find, union
```
- Delegate to: `scipy.cluster.hierarchy.DisjointSet`.
- Traps: no path compression (O(n) finds); union by size/rank ignored; forgetting the same-root early return.
- Tests: all separate, all merged, chain of unions, idempotent union.

### SCC — strongly connected components
- Solves: mutual reachability (cyclic clusters), condensation to a DAG.
- Complexity: O(V+E) (Tarjan or Kosaraju).
- Pure Python: iterative Tarjan (recursive overflows); or delegate.
- Delegate to: `rustworkx.strongly_connected_components`, `scipy.csgraph.connected_components(directed=True, connection="strong")`.
- Traps: recursive Tarjan stack overflow; confusing weak vs strong connectivity.
- Tests: single SCC (one big cycle), all singletons (a DAG), nested cycles.

### MST — Kruskal / Prim
- Solves: minimum-cost spanning tree; single-linkage clustering.
- Complexity: O(E log V).
- Pure Python: Kruskal = sort edges + union-find; Prim = heap frontier.
- Delegate to: `rustworkx.minimum_spanning_tree`, `scipy.csgraph.minimum_spanning_tree`.
- Traps: adding an edge that forms a cycle (DSU guards it); disconnected graph → forest, not tree.
- Tests: tree already minimal, equal weights (any valid MST), disconnected (forest), single node.

### LCA — lowest common ancestor
- Solves: queries over hierarchies (nearest shared ancestor, subtree relations).
- Complexity: O(n log n) preprocess, O(log n) per query (binary lifting); or Euler tour + sparse table.
- Traps: recomputing per query without preprocessing; off-by-one on depth; forgetting the root case.
- Tests: same node, ancestor of the other, root as LCA, deep siblings.
