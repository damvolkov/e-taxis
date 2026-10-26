---
name: algo-py-numeric
description: "Python: numeric computation with efficiency and exactness — vectorization, IEEE-754 floats, fsum, Decimal for money, Welford stats, sparse matrices. Use when statistics, finance or precision matter."
metadata:
  family: design
---

# algo-py-numeric

Numbers, fast and correct at once. Owns vectorization, floating-point exactness, decimal/rational arithmetic, online statistics and sparse algebra. Not here: choosing a plan or assignment under constraints (`algo-py-optim`), ML training and linear algebra for embeddings (`ml`). The stack every example draws on → `references/lib.md`.

## Rules

1. **Vectorize; a Python loop over an array is a bug.** Broadcasting and array ops (NumPy/Polars) replace element loops — SIMD and one dispatch instead of n. Reach order: builtin → NumPy/Polars → JIT. → `references/lib.md`
2. **Never `==` on floats; never `sum` where accuracy matters.** `math.isclose` for comparison; `math.fsum` (Shewchuk) for an accurate sum; know IEEE-754 rounding. → `references/algorithms.md`
3. **Money and exact ratios are not `float`.** `decimal.Decimal` with a fixed context and explicit rounding for currency; `fractions.Fraction` for exact rationals.
4. **Statistics stream incrementally.** Welford for online mean/variance in one pass — never accumulate `sum(x)`/`sum(x²)` and subtract (catastrophic cancellation).
5. **Mind integer overflow and dtype.** NumPy `int64` overflows silently (Python `int` does not); pick the dtype deliberately; `object` dtype in NumPy/Polars defeats the point.
6. **Sparse when mostly empty.** CSR/CSC (`scipy.sparse`) turns O(n²) dense memory into O(nnz); dense only when the fill is real.
7. **Numeric mass runs off the event loop.** NumPy releases the GIL on many ops; still offload heavy work via `to_thread`; JIT (`numba`) an irreducible numeric loop, compiled once at startup. → `conc-py-async`

## Sample

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Welford:
    """Online mean and variance in one pass — numerically stable, O(1) memory."""
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / self.n if self.n else float("nan")
```

One pass, no cancellation, no stored history. The naive `sum(x²)/n - mean²` loses all precision on large near-equal values.

## References

- `references/algorithms.md` — cards: fsum/Kahan, Welford, Decimal contexts, vectorization, sparse formats
- `references/antipatterns.md` — ❌ → ✅ with the cost
- `references/bibliography.md` — the chapters this domain leans on
- `references/lib.md` — the stack: NumPy, Polars, `numba`, `numexpr`, `scipy.sparse`, offload
