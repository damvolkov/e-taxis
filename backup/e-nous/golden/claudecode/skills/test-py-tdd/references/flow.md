# flow — every module born tested

Testing is not a phase after the code; it is a flow that tracks the code's integration state. A module moves through tiers as it becomes part of the system.

## The three tiers

| Tier | Tests | When | Isolation |
|---|---|---|---|
| **unit** | one module/algorithm in isolation | the moment it exists | everything external is a fixture/fake |
| **integration** | the module wired to real collaborators | once it is connected to the system | real store/broker (ephemeral or `slow`), no fakes |
| **acceptance** | the whole system against user-facing behaviour | only when the project is finished | end to end, black box |

`unit` proves the piece is correct; `integration` proves the seams hold; `acceptance` proves the product does what was asked. A module lands in `unit` first and gains an `integration` test the day it stops being standalone — that progression is the discipline, not an optional extra. (`evaluation` and `benchmark` are separate tiers for eval/regression and perf.)

## The loop

Red → green → refactor, per behaviour:

0. Name every way the behaviour could fail — empty, duplicated, out of order, half-written, wrong tenant, the misconfiguration the default protects against. The list is the design; the tests are its transcript.
1. Write the atomic async test for the behaviour you are about to add; watch it fail (red).
2. Write the least code that passes (green).
3. Refactor with the test as the net; the test does not change.

Parametrize the scenarios of one behaviour rather than copy a test; a new test function is for a genuinely different setup or assertion.

## Seen failing, for the right reason

A test that has only ever been green is an assertion about nothing. Break the code it covers — or switch the feature off — and read the failure: it must name the behaviour, not a missing fixture, a bad import or a skip. A red obtained for the wrong reason is the same as no test, and it is the one that survives to production.

The same applies backwards to a test written after the code: it can only confirm what the code already does. If a behaviour arrives untested, delete nothing and add the test — but watch it fail first, against the code with that behaviour disabled.

## Which scenario to pick

At `unit`, the parametrize carries the edge cases and the simplest input is one of them. At `integration` and `acceptance` the simplest scenario is a waste of a slow test: pick a medium-to-hard one — several entities, a restored session, the backwards-compatible shape, the misconfiguration the default exists to prevent. The happy path is proven for free by every other scenario that contains it.

## Trusting what it measures

A harness is code, and an uncalibrated harness reports numbers nobody can defend:

- **Calibrate before you believe it.** Make it reproduce one result the real system is already known to produce. Until it does, what it measures is unnamed.
- **Compare against an untouched baseline.** Run the same suite on the unmodified revision before reading yours — it is the only way to separate what you broke from what was already broken.
- **Record what produced the number**: commit, pinned versions, the command. A measurement you cannot re-run is an anecdote.

## What "integration" means here

Not "unit with more mocks" — the opposite. An integration test uses the **real** collaborator (a container Postgres, a live broker, a `pytest-httpserver`-served HTTP only where a third party can't run locally), and is marked `slow` when it hits something external so the default run stays fast:

```toml
[tool.pytest.ini_options]
markers = ["slow: hits real external services (run: uv run pytest -m slow)"]
```

## Coverage

`>90%` is the floor, checked in CI (`pytest --cov --cov-report=term-missing`), never the goal — coverage counts lines run, not behaviours proven. A parametrized suite that exercises the edge cases beats a high number that exercises the happy path.

## The 100 % gate's usual holes

Under a 100 % branch gate, a `match` without a wildcard arm leaves one uncoverable branch: coverage counts the implicit "no case matched" exit. Add a `case _:` (raising explicitly if nothing else fits) — never lower the gate. The thin `main()` wrapper without its own test is the other standing hole.

## Recording cassettes

When the collaborator is a model or a document converter, integration tests ride recordings, not live nondeterminism:

- **Record at the request boundary, not the document boundary.** A cassette of whole-document conversions breaks the moment span selection shifts. Record each request exactly as the production port issues it — one entry per requested span, keyed by the request — so the fake serves each span its own markdown, like the real thing.
- **The fake keeps the real invariants.** If production guarantees a balance (facts vs totals), the port re-checks it on playback: a misaligned recording must fail loudly, not replay blind.
- **No secrets in cassettes; a cassette lives or dies with its test name.** `grep` the recording for keys before committing; renamed test → renamed cassette, or it silently never plays.
- **When a rerun disagrees, check who is wrong.** Model output drifting against an expected list is evidence: verify the selection against the source first — the assertion may be the bug. Fix it to the exact recorded list, never "close enough".
