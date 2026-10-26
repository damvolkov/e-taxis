# antipatterns — numeric

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| `sum()` of many floats where accuracy matters | rounding error accumulates | `math.fsum` |
| `float` for money | representation error → wrong cents | `decimal.Decimal` with a fixed context |
| `a == b` on floats | spurious inequality | `math.isclose` |
| `Decimal(0.1)` from a float | inherits the float error | `Decimal("0.1")` from a string |
| `sum(x²)/n - mean²` for variance | catastrophic cancellation | Welford online algorithm |
| Python `for` over a NumPy array | interpreter-bound, no SIMD | vectorize / broadcast |
| `.tolist()` on the hot path | array → object round-trip | stay in the array |
| ignoring `int64` overflow | silent wrap-around | pick dtype deliberately, check bounds |
| `object` dtype in NumPy/Polars | defeats vectorization | a concrete numeric dtype |
| dense matrix that is mostly zero | O(n²) memory | `scipy.sparse` CSR/CSC — O(nnz) |
| a solver/blas call on the event loop | blocks the loop | offload via `to_thread` |
