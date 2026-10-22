# fixtures — the reusable, localized, typed

The rule that shapes every test file: **anything reusable is a fixture, in the conftest at its level, the instant it repeats.** A test module contains `async def test_*` and file-local parametrize constants — nothing else. No fixture, helper, factory, mock or loaded file ever lives in a test module.

## conftest hierarchy

A fixture lives at the **narrowest** scope that needs it; wider scope = wider blast radius on change.

```
tests/conftest.py                     # session fixtures the whole system needs (app, event loop, base config)
tests/unit/conftest.py                # unit-wide fakes and helpers (fake_redis, a mock server factory)
tests/unit/<pkg>/<area>/conftest.py   # the business-logic fixtures of THAT area only
tests/unit/<pkg>/<area>/confmodels.py # Polyfactory factories + external API response schemas, beside them
```

The root conftest is for what is genuinely global; business-logic fixtures belong **down in their own subdirectory**, not hoisted to the top. This keeps each area's setup readable and stops the root becoming a dumping ground.

## Typed injection

Fixtures inject by parameter name; type them by importing the class, so the contract is checked and the editor resolves it:

```python
async def test_store_get(store: KnowledgeStore, sample_node: Node) -> None: ...
```

Fixtures are nouns (`store`, `sample_node`, `fake_redis`), never verbs. A fixture may depend on another fixture — compose them, do not rebuild shared setup.

## Data — Polyfactory, not dicts

Every model that represents stored or external data gets a Polyfactory factory in the area's `confmodels.py`; the fixture builds instances from it. Hand-written dicts for domain data drift from the model and skip validation — the factory stays in sync with the type.

## Resources — files behind a fixture

Physical assets (audio, JSON, CSV) live in `tests/resources/<domain>/`, outside the mirror, and load through a fixture:

```python
# tests/unit/adapters/conftest.py
_RES = Path(__file__).parents[3] / "resources" / "audio"

@pytest.fixture
def sample_wav() -> Path:
    return _RES / "hello.wav"
```

A test never opens a path itself; it asks for the resource fixture.

## Scope and order

Declare `scope="session"` for expensive, immutable setup (the app, a container); default function scope for anything a test may mutate. Within a conftest, order fixtures paths/resources → factories → infrastructure → services → data → helpers, so a reader follows the dependency direction top to bottom.
