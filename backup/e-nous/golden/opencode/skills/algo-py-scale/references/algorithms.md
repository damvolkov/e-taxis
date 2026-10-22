# algorithms — scale cards

One card per algorithm. At scale you mostly **delegate to a vetted sketch/string library** and state the error bound; pure-Python appears only where it is short and instructive.

### Reservoir sampling
- Solves: a uniform sample of k items from a stream of unknown length.
- Complexity: O(n) time, O(k) memory, single pass.
- Pure Python: keep the first k, then replace index `j = randint(0, i)` with prob k/(i+1) (see SKILL sample).
- Delegate to: builtin `random`; `random.sample` only when the length is known and it fits.
- Traps: assuming the length is known; biased replacement probability; reseeding mid-stream.
- Tests: k≥n (keep all), k=0, uniformity over many runs (each item ~k/n), n=1.

### HyperLogLog — cardinality
- Solves: count of distinct items with tiny fixed memory.
- Complexity: O(1) memory (KB), ~1–2% relative error; mergeable across shards.
- Delegate to: `datasketches` (HLL or CPC).
- Traps: using a `set` (O(n) memory); expecting an exact count; comparing sketches with different precision.
- Tests: exact count for small n, error within bound for large n, merge of two shards equals union count.

### Bloom / Cuckoo filter — approximate membership
- Solves: "have I seen this?" with no false negatives, tunable false positives.
- Complexity: O(k) per op, memory ~ n·bits; Cuckoo also supports deletion.
- Delegate to: `rbloom` (Rust, set-like); Cuckoo when you need deletes.
- Traps: treating a positive as certain (it is "maybe"); undersizing → false-positive rate explodes; needing deletion with a plain Bloom.
- Tests: no false negatives ever, measured false-positive rate ≤ target, capacity boundary.

### Count-Min / Misra-Gries — heavy hitters
- Solves: approximate frequencies / the most frequent items in a stream.
- Complexity: sublinear memory. Count-Min overestimates; Misra-Gries gives approximate top items with error ε.
- Delegate to: `datasketches` Frequent Items.
- Traps: reading a Count-Min estimate as exact; too few counters for the required ε; ignoring the overestimate direction.
- Tests: exact for a small distribution, top-k matches within ε, skewed vs uniform input.

### t-digest / KLL — streaming quantiles
- Solves: p50/p95/p99 over a stream without storing all values.
- Complexity: sublinear memory; mergeable.
- Delegate to: `datasketches` KLL (rank-error bounded).
- Traps: sorting the whole stream for a percentile; expecting exact quantiles; merging incompatible sketches.
- Tests: quantiles within the rank-error bound vs exact on medium n, monotonic quantiles, merge correctness.

### MinHash + LSH — near-duplicate detection
- Solves: find similar items (Jaccard) without comparing all pairs.
- Complexity: ~O(n) with LSH banding, vs O(n²) all-pairs.
- Delegate to: `datasketch` (MinHash + LSH / LSH Forest).
- Traps: all-pairs comparison; wrong band/row tuning for the similarity threshold; too few permutations (noisy estimate).
- Tests: exact-duplicate pairs always collide, dissimilar pairs rarely collide, estimated Jaccard vs true within tolerance.

### Aho-Corasick — multi-pattern matching
- Solves: find all occurrences of many patterns in one pass.
- Complexity: O(text + total matches) after O(Σ patterns) build.
- Delegate to: `ahocorasick-rs` (Rust) or `pyahocorasick` (C).
- Traps: a loop of `re.search`/`in` per pattern (O(patterns × text)); rebuilding the automaton per query; overlapping-match semantics ignored.
- Tests: overlapping patterns, patterns that are prefixes of each other, no match, patterns at text boundaries.

### Edit distance / fuzzy matching
- Solves: string similarity, typo-tolerant matching, best match in a candidate set.
- Complexity: O(nm) per pair; `process.cdist` parallelizes the many-vs-many case.
- Delegate to: `rapidfuzz` (Levenshtein, Jaro-Winkler, token ratios), `workers=` for batches.
- Traps: hand-rolled Levenshtein in Python (slow); comparing all pairs when LSH/blocking would prune; wrong metric for the task (edit vs token).
- Tests: identical strings score max, one edit apart, transposition, empty string, case/whitespace normalization.

### Myers diff
- Solves: minimal edit script between two sequences (versions, lines).
- Complexity: O((n+m)D), D = edit distance.
- Delegate to: `difflib` (stdlib) for small/medium; external tools for massive diffs.
- Traps: `difflib` on enormous inputs unbounded (quadratic memory); diffing characters when lines suffice; ignoring the move/rename case.
- Tests: identical inputs (empty script), full replacement, single insertion/deletion, common prefix/suffix.
