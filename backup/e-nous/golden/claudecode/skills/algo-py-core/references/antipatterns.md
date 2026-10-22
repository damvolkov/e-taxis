# antipatterns — core

Each is a real O() regression or a reinvention. ❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| `x in a_list` inside a loop | O(n²) | build a `set` once, test membership O(1) |
| `list.pop(0)` / `insert(0, x)` as a queue | O(n) per op | `collections.deque` — O(1) both ends |
| `sorted(items, key=…)[:k]` for small k | O(n log n) | `heapq.nlargest(k, …)` — O(n log k) |
| concat two collections with nested loops | O(n·m) | dict hash join — O(n+m) |
| `s += piece` building a string in a loop | O(n²) | collect and `"".join(pieces)` |
| re-sort per key (`sort(key=a)` then `sort(key=b)` as separate passes with intent to combine) | 2× work, wrong result | one tuple key `key=itemgetter("a","b")` |
| `groupby` without sorting first | silently wrong (adjacent-only) | sort by the key, then `itertools.groupby`; or `defaultdict` |
| exponential recursion (naive Fibonacci, subset sums) | O(2ⁿ) | DP: memoize then tabulate |
| `@cache` on a function with unbounded/unhashable keys | memory leak | `lru_cache(maxsize=N)`, or bound the key space |
| `bisect.insort` in a loop to keep a list sorted | O(n) per insert → O(n²) | `sortedcontainers.SortedList` — O(log n) |
| hand-rolled binary search / heap / counter | bugs + slower | `bisect` · `heapq` · `Counter` |
| materializing a k-way merge to sort it | O(N) memory + O(N log N) | `heapq.merge` — streaming, O(k) memory |
| generate-all-then-filter for constrained search | full exponential blow-up | backtracking with pruning before descent |
| Python loop to sum/select over 10⁶ numbers | interpreter-bound, slow | vectorize with `numpy`/`polars` off the loop |
