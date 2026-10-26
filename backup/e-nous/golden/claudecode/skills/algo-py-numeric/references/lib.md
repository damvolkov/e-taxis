# lib — the numeric stack

What to reach for on numeric computation and exactness. Reach order: **builtin `math`/`decimal`/`statistics` (exactness) → `numpy`/`polars` (mass) → `numba` (irreducible loops)**. NumPy releases the GIL on many ops; offload the heavy cases. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The numeric stack × the nine software categories.

| Category | Numeric stack |
|---|---|
| **API service** | builtin `math`/`decimal` for money/validation; `numpy` only if compute is core |
| **Async worker** | `numpy`/`polars` for batch metrics, offloaded via `to_thread` |
| **ML pipeline** | `numpy` (arrays) + `polars` (aggregations); `scipy.sparse` for sparse features |
| **Agent system** | builtin `math`/`statistics`; small `numpy` for scoring |
| **Voice runtime** | `numpy` on audio frames — vectorized, GIL released, no per-sample Python |
| **CLI tool** | builtin `math`/`statistics` |
| **System script** | builtin `math`/`decimal` — money, sizes, rates |
| **Evaluation harness** | `numpy` + `polars` for metrics; `statistics` for exact small stats |
| **Library** | builtin `math`/`decimal`/`statistics`; `numpy` only if arrays are the API |

## Primary libraries

| Library | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `math` · `decimal` · `fractions` · `statistics` | exactness surface | `fsum`, `isclose`, money, exact ratios, small stats | stdlib |
| `numpy` | vectorized arrays, SIMD, broadcasting | any array math over 10⁴⁺ elements | BSD, C |
| `polars` | Rust dataframe, vectorized aggregations | tabular numeric aggregation; `collect_async()` | MIT, Rust |
| `scipy.sparse` | CSR/CSC sparse matrices + `linalg` | mostly-empty matrices, sparse solves | BSD, C |

Irreducible numeric loop → `numba` `@njit`; large elementwise expression → `numexpr`; GPU arrays → `cupy`; rigorous stats/tests → `scipy.stats`.

**Never:** `sum()` of floats where accuracy matters (`math.fsum`) · `float` for money (`Decimal`) · `==` on floats (`math.isclose`) · a Python loop over a NumPy array · `.tolist()` on the hot path · ignoring `int64` overflow · `object` dtype.

## Offload

Array/tabular mass off the loop: `asyncio.to_thread(np.…)` / `polars` `collect_async()`. JIT loop: compile at startup, run via `to_thread` (`nogil=True`). Details → `conc-py-async`.

## Testing

`pytest`, `hypothesis` for numeric properties within tolerance (`math.isclose`) — a vectorized reduction vs a `math.fsum` reference, Welford vs `statistics.pvariance`. `pytest-benchmark` for vectorization regressions.
