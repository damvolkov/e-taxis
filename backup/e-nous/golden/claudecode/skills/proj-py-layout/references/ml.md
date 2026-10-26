# ml — RAG / inference pipeline

Data flows through stages: ingest → transform → index/infer → retrieve/serve. Modeled on `e-rag` (pipelines + components) and `et-mlapi` (served inference).

```
src/e_<name>/
├── core/                 # settings, logger, store (vector/relational clients)
├── config/
├── models/
│   └── node/             # complex model subdomain: base, schema, scored, matched
├── pipelines/            # base (Pipeline[T_in,T_out]), ingest, retrieve, strategies/
├── components/           # (or retrievers/, processors/) the swappable stages
├── operational/          # scoring, confidence, softmax — the math
├── adapters/             # embedding/LLM/store clients behind ports
└── api/                  # only if served (query endpoint) — else a library/CLI
```

## Non-negotiables

- **Pipeline as the unit** — a `Pipeline[T_in, T_out]` composes named stages (preprocessors → run → postprocessors); a stage is a `Processor`, swappable and tested in isolation → `test-py-tdd`.
- **Components by role, subdomained** — `retrievers/parent.py`, `processors/reranker.py`; one word per implementation, the role is the folder → `tax-py-naming`.
- **The math is `operational/`** — scoring, attenuation, softmax as pure functions (assert on values, no mocks); the algorithms themselves → `algo-py-*`.
- **Models as a subdomain** — a rich model tree (`node/`) lives in `models/node/` with `base`, `schema`, `scored`, `matched`; kinds → `lang-py-datamodel`.
- **Retrieval and vector search** are the `ml` family's concern (embeddings, index, RAG) — named in that `lib.md`; this file is the shape they hang on.
- **Serve or not** — add `api/` to expose inference; otherwise it is a library (`library.md`) or driven by a CLI.
