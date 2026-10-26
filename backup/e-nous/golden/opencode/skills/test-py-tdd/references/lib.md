# lib — the test stack

What to reach for to test. Reach order: `pytest` + builtin fixtures → `pytest-asyncio` (async) → `pytest-mock`/Polyfactory → the service fakes and runner plugins. Assert on values first; mock only a real boundary. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The test stack × the nine software categories — what dominates beyond the core.

| Category | Adds to the core |
|---|---|
| **API service** | `pytest-httpserver` (real local HTTP — `wreq` cannot be intercepted), the framework's test client, `fakeredis` |
| **Async worker** | ephemeral Postgres with `awa` migrated, or broker container (`slow`); `fakeredis`, `pytest-timeout` |
| **ML pipeline** | `hypothesis` for numeric properties, `pytest-benchmark`, resource fixtures |
| **Agent system** | a recorded-LLM fake behind the port, Polyfactory for message models |
| **Voice runtime** | audio resource fixtures, `pytest-benchmark` on the hot path |
| **CLI tool** | the CLI runner (typer/cyclopts), `capsys` for output |
| **System script** | `tmp_path`, `monkeypatch`, `caplog` |
| **Evaluation harness** | `evaluation`/regression tier, `hypothesis`, benchmark |
| **Library** | `hypothesis` for the public contract; matrix across Python versions |

## Primary stack

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `pytest` | the runner + builtin fixtures (`caplog`, `tmp_path`, `monkeypatch`, `capsys`) | always | MIT — house pins `>=9` |
| `pytest-asyncio` | run `async def` tests (`asyncio_mode = "auto"`, no per-test marker) | every suite (tests are async) | Apache-2.0 |
| `pytest-mock` | the `mocker` fixture — patch/spy through a fixture, auto-undone | mocking a real boundary | MIT — never `unittest.mock` |
| `polyfactory` | typed factories for dataclasses/pydantic/msgspec models | any stored/external data fixture | MIT |
| `hypothesis` | property-based tests: compare against a naive oracle, fuzz edges | a function with an invariant or wide input space | MPL-2.0 |
| `pytest-stress` | loop the suite for a time box (`--seconds 60 --delay 1`) — flakiness, async races, leaked state | every async/voice/worker suite, before shipping | MIT — 1.0.1, dormant since 2019 but verified on pytest 9.1 / Py 3.14 (2026-09-28) |

Runner plugins (in `pyproject` `addopts`): `pytest-cov` (>90% gate), `pytest-benchmark` (the `benchmark` tier), `pytest-xdist[psutil]` (`-n auto`), `pytest-randomly` (order-independence), `pytest-timeout` (hang guard), `pytest-stress` (flakiness/race hunt, run explicitly: `pytest --seconds 60 --delay 1`; mandatory-recommended, not in `addopts`). Its README is stale (`-n`/`-d` need xdist, not wired): the real flags are `--seconds/--minutes/--hours/--delay`. Service fakes: `pytest-httpserver` (a real local server is the only honest fake for `wreq` — it exposes no transport), `fakeredis`. Only when the code under test already sits on the httpx-compatible surface: `httpxr.MockTransport` / `httpxr.ASGITransport` (or `httpx2`'s, pure-Python). `respx` mocks legacy `httpx` alone and intercepts neither `wreq` nor `httpxr`. Dates: 2026-09-27 (`pytest-stress` re-verified 2026-09-28).

**Never:** a fixture, helper or factory in a test module · `unittest.mock` (use `mocker`) · a hand-built dict for model data (use Polyfactory) · a test class · a sync test · `open()` a resource inline (use a resource fixture) · asserting on a mock where a value assertion is possible.

## Testing the tests

`asyncio_mode = "auto"` and `-p no:randomly` off by default; `pytest-randomly` surfaces order coupling, `pytest-xdist` surfaces shared-state bugs — a suite that passes under both is isolated. `pytest-stress --seconds 300 --delay 1 -k <suspect>` loops the suite to expose intermittent failures the single pass hides — flaky async tests and lifecycle leaks only repeat runs catch (→ `conc-py-async`, `lang-py-lifecycle`). `make test` / `make cov` wrap this → `ops-gen-make`.
