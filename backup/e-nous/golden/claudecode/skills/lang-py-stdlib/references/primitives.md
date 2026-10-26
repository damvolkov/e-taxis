# primitives — time, identity, randomness

One right module per job; the wrong one is a subtle bug, not a style choice.

## Time — `datetime`, `zoneinfo`, `time`

- **`datetime` + `zoneinfo`** — every datetime that crosses a boundary (stored, logged, sent) is **timezone-aware**, in UTC: `datetime.now(UTC)`. A naive datetime is a bug waiting for a DST change; attach a zone with `ZoneInfo("Europe/Madrid")` only at the display edge. (`zoneinfo` needs the `tzdata` package on Windows.)
- **`time.monotonic()`** — for measuring an interval: it never goes backward, unaffected by clock adjustments. **`time.perf_counter()`** for the highest-resolution duration. Never subtract two `datetime.now()` to time code — the wall clock can jump.
- **`time.time()`** only for a wall-clock epoch stamp, never for durations.

## Identity — `uuid`

- **`uuid4()`** for a random unique id. **`uuid7()`** (3.14) when the id should sort by creation time — time-ordered, index-friendly, the modern default for database keys.
- A ULID or time-ordered id keeps inserts local in a B-tree; `uuid4` scatters them. Choose by whether ordering matters.

## Randomness — `secrets` vs `random`

- **`secrets`** for anything an attacker could exploit: tokens, keys, passwords, nonces (`secrets.token_urlsafe`, `secrets.compare_digest`). Cryptographically strong.
- **`random`** only for simulation, sampling, jitter, shuffling test data — never for a secret. `random.SystemRandom` bridges the two but `secrets` states the intent.
- Seed `random` for reproducible tests; never seed `secrets` (it has no seed, by design).

The rule under all three: the module encodes the guarantee. Reaching for `random` where `secrets` is meant, or `datetime` where `monotonic` is meant, compiles and passes the happy path — then fails in production on the case the wrong guarantee never covered.
