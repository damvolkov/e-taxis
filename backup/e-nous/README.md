# backup/e-nous — the retired transpiler, for reference

The e-nous transpiler (`ops/transpiler`, model v1) and its specs (`specs/`), as they stood at e-nous `2b3b6da`
(branch `feat/taxis-split`), before the single data model v2 (`specsv2/` + `core/schema.yaml` in e-nous) replaced
them. Kept to mine: render and typeset rules, the merge semantics, absorb, the history store, and 256 unit tests
that pin its behaviour. Not runnable here — it imports `ops.*` from e-nous (the `ops/models` and `ops/core` files
beside it are the ones it needs, copied for reading). Never imported, linted or tested by e-taxis.

| Path | Was |
|---|---|
| `ops/transpiler/` | render · typeset · absorb · bridge · origin · map · bench · history/{store,plan,classify,matrix,view} |
| `ops/models/`, `ops/core/` | the spec, history, entity, mcp and graph models; settings and dotted helpers it imports |
| `specs/` | the per-entity spec files of v1 (tekton, nomos), with `ghost.yaml` and `sources.yml` |
| `tests/unit/ops/transpiler/`, `tests/integration-transpiler/` | its suites |

Delete once the new transpiler covers every behaviour listed in e-nous `specsv2/base.yaml`.
