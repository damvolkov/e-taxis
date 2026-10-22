---
name: algo-gen-selector
description: "Gen: algorithmic router — classify a need into an algorithm, its complexity and the owning skill. Use before writing non-trivial sort, search, dedup, graph, recursion, big-data or optimization code."
metadata:
  family: design
---

# algo-gen-selector

Classify, don't implement. Turn a vague need into a named algorithm, its real complexity and the one skill that owns it. Restate the need as input → output, size (n, m), fits in RAM?, streaming?, exact or approximate; look it up in `references/problem_catalog.md`; pick the domain with the tree below (ties → the domain that drives the complexity, reference the other); load that skill and emit the derivation card before any code.

## Decision tree

```
relations / dependencies between elements (who depends on whom, paths, cycles, connected groups)?
  └─ yes → algo-py-graphs
data that won't fit in RAM, arrives as a stream, or an approximate answer at scale suffices?
  └─ yes → algo-py-scale
choosing a best assignment / plan / schedule under constraints?
  └─ yes → algo-py-optim
numeric computation, floating-point exactness, sparse or mass arithmetic?
  └─ yes → algo-py-numeric
otherwise — sort, search, group, dedup, recursion, DP, greedy, backtracking, two-pointers, prefix sums
  └─ → algo-py-core
```

## Rules

1. **Better O() ≠ faster in production.** Constants, cache locality and vectorization dominate at real sizes. Choose and delegate; never implement a paper (Duan 2025 SSSP beats Dijkstra in theory, not in evaluated practice).
2. **In Python the cost is interpreter work.** O(n log n) in C/Rust beats O(n) in pure Python up to large n. Reach order: builtin > Rust-backed > C/C++ > pure Python.
3. **Measure before optimizing.** `timeit`, `cProfile`, `pyinstrument`, `memray`/`tracemalloc`. Never assert a speedup unmeasured.
4. **Unbounded recursion depth → explicit stack/queue.** Python has no TCO; never raise the recursion limit. → `para-py-iteration`
5. **CPU-bound work never on the event loop.** Offload to thread/process. → `conc-py-async`
6. **Exactness and determinism are requirements, not extras.** Stable order, fixed seeds, `fsum`/`Decimal` where it matters. → `algo-py-numeric`
7. **Don't reinvent.** If a builtin or a vetted library already solves it, use it; each domain `lib.md` names which.

## Sample

```markdown
Derivation card — emit before coding:
- Need: deduplicate 40M event ids arriving as a stream
- Size / memory / stream / exactness: n≈4e7, > RAM, streaming, approx OK (≤1% error)
- Algorithm: HyperLogLog (cardinality) | Complexity: time O(n), memory O(1)
- Target skill: algo-py-scale
- Rejected alternative: `set` of ids — O(n) memory, blows RAM
```

## References

- `references/domain_map.md` — the domains, their core algorithms, the single owner skill, size thresholds
- `references/problem_catalog.md` — Skiena-style need → signal → algorithm → complexity → skill
- `references/bibliography.md` — reference literature by level
- No `lib.md` — this router only classifies and delegates; the domain skills own the vendors.
