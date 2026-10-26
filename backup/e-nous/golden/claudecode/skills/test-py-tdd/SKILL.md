---
name: test-py-tdd
description: "Python: test-driven flow and fixture-oriented pytest — unit→integration→acceptance, atomic async tests, conftest hierarchy, Polyfactory, resources. Use when writing or organizing tests."
metadata:
  family: quality
---

# test-py-tdd

Every module is born tested, and every reusable thing is a fixture. This skill owns the testing *method* and the fixture architecture; the src-mirror tree and test naming are `tax-py-naming` (referenced, never repeated). Pure cores you assert on without mocks come from `arch-py-adt`; the plugin stack → `references/lib.md`.

## Rules

1. **Test as a flow: unit → integration → acceptance.** A new module/algorithm is tested the moment it exists — unit in isolation first; integration once wired to the rest of the system; acceptance only when the project is whole. The flow is the discipline, and a test nobody watched fail for the right reason is not a test. → `references/flow.md`
2. **Atomic async tests, never classes.** Every test is `async def test_*() -> None`, one behaviour; no test classes, no sync tests. Parametrize is the default; a scenario function exists only when setup or assertions truly differ. Tree and names → `tax-py-naming`.
3. **Fixture-oriented: reusable → fixture, immediately.** Any object, resource, fake or shared constant that repeats becomes a fixture in the conftest at its level the instant it repeats. A test module holds tests and nothing else — never a fixture, helper or factory. → `references/fixtures.md`
4. **conftest hierarchy mirrors scope.** `tests/conftest.py` = session fixtures the whole system needs; `tests/unit/conftest.py` = unit-wide; each subdirectory's business-logic fixtures live in *that subdirectory's* conftest — the narrowest level that needs them. → `references/fixtures.md`
5. **Inject by name, type by class.** Fixtures auto-inject; the test imports the class only for the annotation (`store: Store`), so the contract is checked and the IDE resolves it. Model/storage data → Polyfactory factories in `confmodels.py`, never hand-built dicts. → `references/fixtures.md`
6. **`resources/` and `benchmark/` always exist.** `tests/resources/` holds the physical files loaded as resource fixtures (never an ad-hoc `open` in a test); `tests/benchmark/` holds perf tests. Both created from the start, empty if unused.
7. **Mock through fixtures, assert on values — never on calls.** `mocker` (pytest-mock), `caplog` for logs, `pytest-httpserver`/`fakeredis` for services — the plugin, never `unittest.mock`; and prefer a pure core that needs no mock at all. Asserting a collaborator *was called with what you passed it* restates the code: it dies at the next refactor and catches no bug. → `references/antipatterns.md` · `references/lib.md`

## Sample

```python
# tests/unit/pipelines/conftest.py — business fixtures beside their tests, never in the module
import pytest
from myapp.pipelines.ingest import IngestPipeline

@pytest.fixture
def ingest(sample_store: Store) -> IngestPipeline:        # composes a session-scoped fixture
    return IngestPipeline(store=sample_store)

# tests/unit/pipelines/test_ingest.py — only tests live here
import pytest

@pytest.mark.parametrize(
    ("rows", "expected"), [([], 0), ([R1], 1), ([R1, R1], 1)],
    ids=["empty", "one", "dedup"],
)
async def test_ingest_run(ingest: IngestPipeline, rows: list[Row], expected: int) -> None:
    assert await ingest.run(rows) == expected
```

The fixture lives in the subdirectory conftest, typed and composed; the module is nothing but a parametrized atomic async test injecting it.

## References

- `references/flow.md` — the unit→integration→acceptance flow, the red-green-refactor loop, seen failing for the right reason, which scenario to pick, trusting a harness, cassettes for model/document collaborators, 100 % gate holes
- `references/fixtures.md` — fixture-oriented discipline, conftest hierarchy, confmodels/Polyfactory, resource fixtures, scopes
- `references/antipatterns.md` — tautological and change-detector tests, asserting on internals, regression bloat, sleeps, a weakened red
- `references/lib.md` — the stack: pytest, asyncio, mock, polyfactory, coverage, benchmark, service fakes
