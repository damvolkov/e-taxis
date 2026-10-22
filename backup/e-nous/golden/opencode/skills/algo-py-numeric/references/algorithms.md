# algorithms — numeric cards

One card per technique. Prefer builtins for exactness, vectorization for mass. Delegate per `lib.md`.

### Accurate summation — fsum / Kahan
- Solves: summing many floats without accumulating rounding error.
- Complexity: O(n).
- Pure Python: `math.fsum(values)` — exact IEEE-754 rounding of the total (Shewchuk).
- Delegate to: `math.fsum` (builtin); `numpy` pairwise sum is accurate but not exact — `fsum` when it must be.
- Traps: `sum()` on a long list of small + large magnitudes (loses low bits); comparing the result with `==`.
- Tests: alternating large/small values, known exact total, order-independence within tolerance.

### Welford — online mean/variance
- Solves: mean and variance in one pass, numerically stable, mergeable.
- Complexity: O(1) per item, O(1) memory.
- Pure Python: see SKILL sample; merge two accumulators by combining `n`, `mean`, `m2`.
- Delegate to: `statistics.mean`/`pvariance` for small resident data; Welford for streams or parallel merge.
- Traps: `sum(x²)/n - mean²` (catastrophic cancellation); population vs sample variance (`n` vs `n-1`); empty input.
- Tests: constant input (variance 0), known distribution, merge equals single-pass, n=0/1.

### Decimal contexts — money
- Solves: exact decimal arithmetic with controlled rounding.
- Pure Python: set a `decimal.Context(prec=…, rounding=ROUND_HALF_EVEN)`; keep money in `Decimal` from parse to format.
- Traps: constructing `Decimal(0.1)` from a float (inherits float error — use `Decimal("0.1")`); mixing float and Decimal; default context precision surprises.
- Tests: rounding at the half, accumulation of cents, currency with 0/2/3 decimals, parse from string not float.

### Vectorization
- Solves: apply an operation across an array without a Python loop.
- Complexity: O(n) with a low constant (SIMD, one dispatch).
- Pure Python: `numpy` broadcasting / `polars` expressions; replace the loop with an array expression.
- Delegate to: `numpy`/`polars`; `numexpr` for large elementwise expressions; `numba` only when the loop cannot be vectorized.
- Traps: a Python `for` over `ndarray`; `.tolist()` round-trips; wrong dtype (upcasting, `object`); `int64` overflow.
- Tests: shape/broadcast correctness, dtype preserved, matches a scalar reference elementwise, overflow boundary.

### Sparse matrices — CSR/CSC
- Solves: matrices that are mostly zero.
- Complexity: O(nnz) memory and matvec, vs O(n²) dense.
- Delegate to: `scipy.sparse` (CSR for row ops / matvec, CSC for column ops, COO for building); `scipy.sparse.linalg` for solves.
- Traps: densifying by accident (`.toarray()`); wrong format for the access pattern; building incrementally in CSR (use COO/LIL then convert).
- Tests: matvec vs dense equivalent, format round-trip, all-zero and all-dense edge cases.
