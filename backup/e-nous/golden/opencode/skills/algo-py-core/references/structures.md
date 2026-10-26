# structures — real cost of the builtins

Choose the structure by the operation you repeat, not by habit. All costs are CPython (see Python Wiki: TimeComplexity).

| Structure | O(1) / cheap | O(n) / trap | Reach for it when |
|---|---|---|---|
| `list` | index, append, pop from end | `insert(0)`, `pop(0)`, `x in list`, `del l[0]`, slicing (copies) | ordered, index-addressed, append-only |
| `dict` | get/set/`in`/del by key | copy, iteration order-sensitive rebuilds | key → value, dedup keeping order (`dict.fromkeys`) |
| `set` / `frozenset` | add, `in`, discard, set ops | — | membership, dedup, intersection/union |
| `collections.deque` | append/pop **both ends** | random index (O(n)) | FIFO queue, sliding window, ring buffer (`maxlen`) |
| `collections.Counter` | count, `most_common` | — | frequency, multiset |
| `collections.defaultdict` | grouped insert | — | group-by, adjacency lists |
| `array.array` | compact numeric storage | no vector ops (that is NumPy) | large homogeneous numeric buffer, low memory |
| `str` / `bytes` | index, len | concatenation in a loop (O(n²)) — use `"".join` | immutable text; build with `join` or `io.StringIO` |
| `heapq` on a `list` | push/pop O(log n), peek O(1) | arbitrary removal O(n) | priority queue, top-k, k-way merge |

## Traps that turn O(n) into O(n²)

- `x in a_list` inside a loop → build a `set` once, test against it.
- `list.pop(0)` / `list.insert(0, x)` as a queue → `collections.deque`.
- `total_str += piece` in a loop → collect and `"".join(pieces)`.
- `del items[i]` in a loop over `items` → build a new list by comprehension, or filter lazily.
- Repeated `min`/`max` scans to maintain an extreme → a heap, or track it incrementally.

## Choosing between ordered options

- Need order **and** fast membership → `dict` (insertion-ordered, O(1) lookup).
- Need a **mutable always-sorted** collection with O(log n) insert and range queries → `sortedcontainers.SortedList` (not `bisect.insort` on a list, which is O(n) per insert).
- Need only to **search/insert into an already sorted list** infrequently → `bisect`.
- Need the **k smallest/largest**, not full order → `heapq.nsmallest`/`nlargest`.
