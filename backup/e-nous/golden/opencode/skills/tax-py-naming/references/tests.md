# Tests

## Mirror

```
src/<pkg>/<path>/<name>.py   ↔   tests/<tier>/<pkg>/<path>/test_<name>.py
```

`<tier>` ∈ `unit`, `integration`, `evaluation`, `acceptance`, `benchmark`. It is the only segment inserted. Everything else is copied character for character.

- `<path>` is never flattened. `backends/native/` exists → `tests/unit/<pkg>/backends/native/` exists.
- The filename never absorbs the path. `test_native_toml.py` is the same error as `sample_adapter.py`.
- Several aspects of one module → suffix, never prefix: `test_entities_ingest.py`, `test_entities_match.py`.
- `conftest.py` at every level that needs fixtures. `confmodels.py` beside it for Polyfactory factories. `resources/` hangs off `tests/`, outside the mirror.

## Economy

```
test_<target>_<scenario>[_<aspect>]
```

The target drops whatever the module path already states. In `tests/unit/providers/test_minio.py`, the class `AgnosticMinioProvider` is tested as `test_agnosticminio_*`: `Provider` is redundant with the module, so it goes.

| Source | Test |
|---|---|
| `get_session()` in `api/deps.py` | `test_get_session` |
| Scenario needing its own function | `test_get_session_auth` |
| Deeper aspect | `test_get_session_auth_expired` |
| `IngestPipeline.run()` in `pipelines/ingest.py` | `test_ingest_run` |
| `AgnosticMinioProvider` in `providers/minio.py` | `test_agnosticminio_stress` |
| Competing intent on the same target | `test_agnosticminio_stress_concurrent` |

A third segment appears only when two tests share target and scenario but differ in intent.

## Shape

- Every test `async def test_*() -> None`. Never test classes.
- Parametrize is the default; a scenario suffix exists only when setup, assertions or side effects genuinely differ.
- Always `ids=[]`.
- Fixtures are nouns: `fake_redis`, `sample_session`.
- Section headers inside a test file follow the same rule as source: `##### QUERY — MOCK SERVER #####`.
