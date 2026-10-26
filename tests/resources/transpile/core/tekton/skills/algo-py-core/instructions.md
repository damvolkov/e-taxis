The base layer: pick the right builtin structure and the right paradigm, and know the real cost inside the interpreter. Owns search & sort, hashing & sets, and the design paradigms. Not here: graphs (`algo-py-graphs`), data > RAM or approximate (`algo-py-scale`), numeric mass (`algo-py-numeric`), constrained optimization (`algo-py-optim`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Know the builtin cost before choosing it.** `x in list` and `list.pop(0)`/`insert(0)` are O(n), slicing copies, `dict`/`set` lookup is O(1). Membership and dedup are a `set`; a FIFO is a `deque`. → `references/structures.md`
2. **Sort once, with a key.** `list.sort`/`sorted` are stable and adaptive (Powersort exploits existing runs); multi-key = one tuple key, never repeated sorts; `key=` over `cmp_to_key`.
3. **Ordered data is `bisect`; top-k is `heapq`.** Binary search to find/insert, binary search over the answer; `heapq.nlargest`/`nsmallest` for top-k without sorting all; `heapq.merge` for k-way merge; quickselect for an exact median.
4. **Hashing is the default for dedup, join, group, count.** `dict.fromkeys` (order-keeping dedup), dict hash join, `Counter`, `defaultdict`; `itertools.groupby` only on already-sorted data.
5. **Paradigms in order.** DP: memo (`functools.cache`) → tabulation → space reduction; backtracking with pruning; greedy only with a proved exchange argument; divide & conquer; two-pointers and prefix sums for range/window work. → `references/algorithms.md`
6. **Recursion → iteration when depth is unbounded.** Python has no TCO; use an explicit stack/`deque`. `@cache` only over a bounded key space — unbounded keys leak memory. Memo that must outlive the call → `data-py-cache`. → `para-py-iteration`
7. **Delegate at scale.** Mass sort/unique/top-k on 10⁶⁺ items → NumPy/Polars off the hot path; never hand-roll what `bisect`/`heapq`/`Counter` already give. → `references/lib.md`

## Sample

```python
from collections import Counter
from heapq import nlargest

def top_senders(events: list[Event], k: int = 10) -> list[tuple[str, int]]:
    """The k most frequent senders — one pass to count, a heap for the top-k."""
    counts = Counter(e.sender for e in events)          # O(n), hashing
    return nlargest(k, counts.items(), key=lambda kv: kv[1])   # O(n log k), not a full sort
```

`Counter` counts in one pass; `nlargest` keeps only a k-heap. A `sorted(...)[:k]` here would be O(n log n) and materialize the whole order. Every name is fixed by `references/lib.md`.

## References

- `references/structures.md` — builtin cost table (`list`/`dict`/`set`/`deque`/`str`/`array`) and the traps
- `references/algorithms.md` — cards: sort, binary search, heap/top-k, k-way merge, quickselect, prefix sums, two-pointers, DP, backtracking, greedy
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the chapters this domain leans on
- `references/lib.md` — the stack: builtins, sorted containers, vectorized fallback, offload, profiling
