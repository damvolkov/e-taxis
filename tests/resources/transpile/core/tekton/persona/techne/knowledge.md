Three layers, each references the one below, never duplicates it:
**Layer 3** patterns (design/agentic) → **Layer 2** algorithms → **Layer 1** Python/Rust efficiency (iteration, resources, async).
Implementation order everywhere: builtin > Rust-backed > C/C++ > pure Python. Async-first.

**Algorithmic rule (always applies).** Before writing nested loops, recursion, sorting, deduplication, data joins, dependency or graph traversal, mass computation, or processing data of non-trivial size: load `algo-gen-selector` to name the algorithm and the domain skill. Signals — implicit O(n²), `x in list` inside a loop, `list.pop(0)`, deep or un-memoized recursion, concatenation in a loop, data that may not fit in RAM, or the words *unique, duplicate, top-k, sort, dependency, path, cycle, frequency, similar, window, schedule, optimize, assign*. Never optimize without measuring; never implement what a builtin or a vetted library already provides.
