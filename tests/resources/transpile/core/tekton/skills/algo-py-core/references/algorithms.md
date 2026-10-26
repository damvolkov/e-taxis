# algorithms — core cards

One card per algorithm. Pure-Python reference is ≤25 lines and iterative when depth is unbounded. Delegate per `lib.md`.

### Stable sort with a key
- Solves: order by one or many criteria.
- Preconditions: a total order via `key`; ties keep input order (stable).
- Complexity: O(n log n); near O(n) on already-sorted runs (Powersort, CPython 3.11+).
- Pure Python: `records.sort(key=itemgetter("dept", "salary"))` — one tuple key, never two passes.
- Delegate to: `list.sort`/`sorted` (builtin); `numpy.argsort` / `polars.sort` for numeric mass.
- Traps: sorting repeatedly per key instead of a tuple; `cmp_to_key` when a key expression exists; forgetting stability guarantees a deterministic tie order.
- Tests: empty, one element, all-equal keys, already sorted, reverse sorted, duplicates.

### Binary search — `bisect`
- Solves: find/insert position in ordered data; search over a monotonic answer space.
- Preconditions: the sequence (or the predicate) is monotonic.
- Complexity: O(log n).
```python
from bisect import bisect_left


def first_ge(a: list[int], target: int) -> int:
    """Index of the first element ≥ target, len(a) if none."""
    return bisect_left(a, target)
```
- Delegate to: `bisect` (with `key=` on 3.10+); `numpy.searchsorted`.
- Traps: linear scan on sorted data; off-by-one between `bisect_left`/`bisect_right`; searching an unsorted list.
- Tests: empty, target below/above all, exact hit, duplicates (left vs right).

### Top-k with a heap
- Solves: the k largest/smallest of n without ordering all n.
- Complexity: O(n log k); memory O(k).
```python
from heapq import nlargest


def top_k(items: list[T], k: int, key) -> list[T]:
    """The k items with the highest key, largest first."""
    return nlargest(k, items, key=key)
```
- Delegate to: `heapq.nlargest`/`nsmallest`; `numpy.argpartition` (O(n)) for numeric.
- Traps: `sorted(items, key=…)[:k]` (O(n log n)); rebuilding the heap each step; unstable ties when order matters.
- Tests: k=0, k≥n, all-equal keys, n=1.

### k-way merge
- Solves: merge k already-sorted sequences into one sorted stream.
- Complexity: O(N log k), memory O(k) — streams, never materializes.
- Pure Python: `heapq.merge(*sorted_iterables, key=key)`.
- Delegate to: `heapq.merge` (builtin, lazy); `asl.merge` for async sources → `para-py-iteration`.
- Traps: concatenate-then-sort (O(N log N) + full materialization); inputs not individually sorted.
- Tests: one empty stream, all empty, single stream, interleaved duplicates.

### Quickselect — exact median/percentile
- Solves: the k-th order statistic without a full sort.
- Complexity: O(n) average, O(n²) worst (mitigate with a random pivot).
- Delegate to: `statistics.median` (small/clear); `numpy.partition`/`percentile` (mass); custom only when neither fits.
- Traps: sorting everything for one percentile; adversarial input on a fixed pivot; ignoring even/odd median convention.
- Tests: n=1, all-equal, even vs odd length, k at both extremes.

### Prefix sums
- Solves: repeated range aggregation over a static array.
- Complexity: O(n) build, O(1) per query.
```python
from itertools import accumulate

pre = [0, *accumulate(values)]  # pre[j] - pre[i] == sum(values[i:j])
```
- Delegate to: `itertools.accumulate`; `numpy.cumsum` for mass; a Fenwick tree only if values mutate.
- Traps: re-summing each query (O(nq)); off-by-one on the half-open range; using it when the array mutates often.
- Tests: empty, single element, full-range query, adjacent equal bounds (zero-width).

### Two-pointers / sliding window
- Solves: subarray/substring meeting a monotone condition, pair-with-sum on sorted data.
- Complexity: O(n).
- Traps: nested loops (O(n²)) where one pass suffices; window invariant not actually monotone; forgetting to shrink from the left.
- Tests: empty, no valid window, whole array valid, minimal window at an edge.

### Dynamic programming
- Solves: overlapping subproblems with optimal substructure.
- Complexity: states × transition cost.
- Progression: memoize the recurrence (`functools.cache`) → tabulate bottom-up → reduce space to the rolling rows actually read.
```python
from functools import cache


@cache
def ways(n: int) -> int:
    """Number of ways to climb n steps taking 1 or 2 — bounded key space."""
    return 1 if n < 2 else ways(n - 1) + ways(n - 2)
```
- Delegate to: builtin `functools.cache` for memo; hand-written table for tight loops.
- Traps: `@cache` over an unbounded/unhashable key space (memory leak); recomputing without memo (exponential); keeping the full table when two rows suffice.
- Tests: base cases, a value with a known closed form, monotonicity of the result, memory bound.

### Backtracking with pruning
- Solves: enumerate combinations/permutations under constraints.
- Complexity: bounded exponential — pruning is what makes it tractable.
- Pure Python: recurse only when a partial solution is still feasible; prune before descending, not after.
- Delegate to: `itertools.product`/`permutations`/`combinations` when there is no pruning; backtracking only when constraints cut the tree.
- Traps: generate-all-then-filter (no pruning); mutating shared state without undo; missing the feasibility check before recursion.
- Tests: no solution, unique solution, symmetry (dedupe equivalent branches), small exhaustive oracle.

### Greedy
- Solves: build the optimum by locally optimal choices — only when an exchange argument proves it.
- Complexity: typically O(n log n) (the sort dominates).
- Traps: assuming greedy is optimal without proof (use DP if unsure); wrong sort key; ignoring counterexamples at boundaries.
- Tests: the case where greedy fails for the naive key, ties, already-optimal input, compare to a brute-force optimum on small n.
