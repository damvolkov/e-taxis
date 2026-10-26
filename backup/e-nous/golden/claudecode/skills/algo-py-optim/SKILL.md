---
name: algo-py-optim
description: "Python: best plan or assignment under constraints — interval scheduling, knapsack, bin packing, LP/MIP, CP-SAT, continuous optimization. Use when scheduling, assigning resources or packing capacity."
metadata:
  family: design
---

# algo-py-optim

Choosing the best option among many under constraints. Owns scheduling, packing, assignment and mathematical optimization. Not here: numeric computation and exactness (`algo-py-numeric`), ML training (`ml`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Name the problem class first.** Interval scheduling, knapsack, bin packing, assignment/matching, LP/MIP, or constraint programming — the class decides the tool. → `references/algorithms.md`
2. **Greedy only when proved.** Interval scheduling by earliest finish time is provably optimal; most greedy schemes are not — prove the exchange argument or use DP/a solver.
3. **Knapsack is DP; bin packing is heuristic.** 0/1 knapsack = pseudo-polynomial DP; bin packing is NP-hard → First-Fit-Decreasing and say the result is approximate, never "optimal".
4. **Complex constraints → a solver, modeled not hand-rolled.** Shifts, routing, allocation → CP-SAT (`ortools`); linear objectives → LP/MIP. Model the variables and constraints; let the solver search.
5. **Every solver call is bounded.** A time limit, an accepted optimality gap, and a feasible fallback — never an unbounded search.
6. **Continuous optimization is `scipy.optimize`.** Scale the variables, pass gradients/constraints explicitly; check convergence, don't trust it.
7. **Solvers never run on the event loop.** Offload to a process with the time limit. → `conc-py-async`

## Sample

```python
def schedule(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Max set of non-overlapping intervals — greedy by earliest finish, provably optimal."""
    chosen: list[tuple[int, int]] = []
    end = float("-inf")
    for start, finish in sorted(intervals, key=lambda iv: iv[1]):   # sort by finish time
        if start >= end:
            chosen.append((start, finish))
            end = finish
    return chosen
```

Earliest-finish-first is the one greedy order with a proof; any other key breaks optimality. When the constraints grow past this, stop hand-rolling and model it for a solver.

## References

- `references/algorithms.md` — cards: interval scheduling, knapsack, bin packing, assignment, LP/MIP, CP-SAT, continuous
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the chapters this domain leans on
- `references/lib.md` — the stack: `ortools`, `scipy.optimize`, builtins, offload
