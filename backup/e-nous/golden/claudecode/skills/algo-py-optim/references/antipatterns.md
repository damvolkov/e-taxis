# antipatterns — optimization

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| brute-force an NP-hard problem | exponential blow-up | DP (knapsack), heuristic (packing), or a solver |
| greedy called "optimal" without proof | silently suboptimal | prove the exchange argument, or use DP/solver |
| interval scheduling sorted by start/length | wrong result | sort by earliest finish time |
| ratio-greedy for 0/1 knapsack | suboptimal (only fractional is greedy) | pseudo-poly DP |
| hand-rolled Hungarian / simplex | bugs, slow | `scipy.optimize` |
| MIP/CP-SAT with no time limit | unbounded run | `max_time_in_seconds` + accepted gap |
| first feasible taken as optimal | leaves value on the table | read the solver's best-bound / objective |
| solver on the event loop | blocks everything | offload to a process |
| unscaled variables in continuous optimization | poor convergence | scale variables, pass the gradient |
