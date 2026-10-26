# lib — the optimization stack

What to reach for when planning, packing or assigning under constraints. Reach order: **builtins (greedy/DP) → `scipy.optimize` (continuous, LP, assignment) → `ortools` CP-SAT (constraints, MIP)**. Solvers are CPU-bound: offload to a process. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The optimization stack × the nine software categories.

| Category | Optimization stack |
|---|---|
| **API service** | builtins for interval/greedy; `ortools` only if optimization is the product |
| **Async worker** | `ortools` CP-SAT in a process with a time limit — the scheduling job |
| **ML pipeline** | `scipy.optimize` for tuning; `scipy.optimize.linear_sum_assignment` for matching |
| **Agent system** | builtins for simple assignment; `ortools` for constrained task allocation |
| **Voice runtime** | builtins only — greedy scheduling, no solver on the audio path |
| **CLI tool** | builtins; `ortools`/`scipy` when the tool solves a planning problem |
| **System script** | builtins for packing/scheduling glue |
| **Evaluation harness** | `scipy.optimize` for parameter search over metrics |
| **Library** | builtins; a solver dependency only if optimization is the library's purpose |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `heapq` · `bisect` · `functools` | greedy, interval scheduling, DP tables | the class has a proven greedy or a small DP | stdlib |
| `scipy.optimize` | continuous optimization, `linprog` (HiGHS), `linear_sum_assignment` | continuous fitting, linear programs, one-to-one assignment | BSD, C |
| `ortools` | CP-SAT and MIP solver | shifts, routing, allocation, hard combinatorial constraints | Apache-2.0, C++ (Google) |

Modeling front-ends (`pulp`, `pyomo`, `cvxpy`) only when a solver-agnostic model is worth the layer. Reach for a new tool only when these three do not fit.

**Never:** brute-force an NP-hard problem · call greedy "optimal" without a proof · run a solver with no time limit · block the event loop with a solve.

## Offload

CP-SAT/MIP → `run_in_executor(ProcessPoolExecutor)` or `anyio.to_process`, with `max_time_in_seconds` and a solution callback. Process/thread details → `conc-py-async`.

## Testing

`pytest`. `hypothesis` checking solver output against a brute-force optimum on small instances and asserting constraint feasibility. `pytest-benchmark` with a fixed time limit for solve-time regressions.
