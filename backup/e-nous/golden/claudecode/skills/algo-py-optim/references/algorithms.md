# algorithms — optimization cards

One card per problem class. Recognize the class, then pick greedy / DP / heuristic / solver. Delegate per `lib.md`.

### Interval scheduling
- Solves: maximum set of non-overlapping intervals.
- Complexity: O(n log n) (the sort dominates).
- Pure Python: greedy by earliest finish time (see SKILL sample) — provably optimal.
- Traps: sorting by start or by length (breaks optimality); weighted intervals need DP, not greedy.
- Tests: no overlap, total overlap, nested intervals, equal finish times, weighted variant → DP.

### 0/1 knapsack
- Solves: maximize value within a capacity, items indivisible.
- Complexity: O(n·W) pseudo-polynomial DP.
- Pure Python: 1-D DP over capacity, iterate capacity descending to keep items 0/1.
- Delegate to: `ortools` when constraints grow beyond a single capacity.
- Traps: greedy by value/weight ratio (optimal only for fractional knapsack); huge W makes DP infeasible → solver; forgetting the descending capacity loop.
- Tests: zero capacity, one item fits/doesn't, ratio-greedy counterexample, capacity exactly filled.

### Bin packing
- Solves: pack items into the fewest fixed-capacity bins.
- Complexity: NP-hard; First-Fit-Decreasing is ~11/9·OPT.
- Pure Python: sort descending, place each in the first bin that fits.
- Traps: presenting a heuristic result as optimal; not sorting descending; ignoring that exact packing needs a solver.
- Tests: items equal to capacity, all tiny, one oversized (infeasible), FFD vs known optimum on small sets.

### Assignment / matching
- Solves: optimal one-to-one assignment (workers↔tasks), min cost or max weight.
- Complexity: polynomial (Hungarian / flow).
- Delegate to: `scipy.optimize.linear_sum_assignment`; bipartite matching / max-flow → `algo-py-graphs`.
- Traps: hand-rolling the Hungarian algorithm; rectangular cost matrix mishandled; confusing max-weight with min-cost (negate).
- Tests: square vs rectangular, forbidden pairs (inf cost), unique optimum, ties.

### Linear / integer programming (LP/MIP)
- Solves: linear objective under linear constraints; MIP adds integrality.
- Complexity: LP polynomial; MIP NP-hard.
- Delegate to: `scipy.optimize.linprog` (LP, HiGHS backend); `ortools` for MIP.
- Traps: no time limit / gap on MIP; unbounded or infeasible model unchecked; unscaled coefficients hurting the solver.
- Tests: known LP optimum, infeasible model detected, integrality actually enforced, bounded solve time.

### Constraint programming — CP-SAT
- Solves: scheduling, rostering, routing, allocation with rich logical constraints.
- Complexity: NP-hard; CP-SAT searches with a time limit.
- Delegate to: `ortools` CP-SAT — declare variables and constraints, set `max_time_in_seconds`, read the best feasible solution.
- Traps: no time limit; assuming the first feasible is optimal; missing a redundant constraint that would prune the search; solving on the event loop.
- Tests: tiny instance vs brute-force optimum, feasibility of the returned solution, time-limit respected, infeasible model reported.

### Continuous optimization
- Solves: minimize a continuous function, possibly constrained.
- Complexity: problem-dependent (convex → tractable).
- Delegate to: `scipy.optimize.minimize` (pass the gradient and constraints; scale variables).
- Traps: comparing floats for convergence; unscaled variables; local minimum mistaken for global on a non-convex objective.
- Tests: known analytic minimum, constraint active at the optimum, convergence tolerance, scaled vs unscaled.
