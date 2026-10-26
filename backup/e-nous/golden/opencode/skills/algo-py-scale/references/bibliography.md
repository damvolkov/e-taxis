# bibliography — scale

The chapters this domain leans on. Full canon → `algo-gen-selector` `references/bibliography.md`.

| Work | Chapters | For |
|---|---|---|
| *Algorithms and Data Structures for Massive Datasets* (Manning, 2022) | streaming; sketches; external memory | the whole domain |
| Leskovec, Rajaraman, Ullman, *Mining of Massive Datasets* (free) | data streams; finding similar items (MinHash, LSH) | similarity and streaming |
| Gakhov, *Probabilistic Data Structures and Algorithms for Big Data* | Bloom; HyperLogLog; Count-Min | the sketches, with error analysis |
| Slotin, *Algorithms for Modern Hardware* (free) | memory hierarchy; SIMD | why cache and columnar layout dominate |
| Kleppmann, *Designing Data-Intensive Applications* | storage & retrieval; partitioning | bridge to Layer 3 |
| Apache DataSketches docs | HLL, KLL, Theta, Frequent Items | correct sketch selection and merging |
| Polars docs | streaming engine; lazy API | out-of-core execution |
| DuckDB docs | out-of-core execution | ad-hoc SQL over > RAM |
