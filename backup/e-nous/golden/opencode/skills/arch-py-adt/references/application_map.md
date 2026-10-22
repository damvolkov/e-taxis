# Application map — modeling patterns per software category

For each of the nine software categories (→ `AGENTS.md`), which modeling patterns pull their weight. `P` = primary (reach for it by default) · `S` = secondary (when the case appears) · `—` = rarely.

| Category | Sum types / ADT | Result / railway | Newtype / parse | State machine | Functional core |
|---|---|---|---|---|---|
| **API service** | P (DTOs, events) | S (service layer) | P (ids, validated fields) | S (session/resource status) | S (use-case decisions) |
| **Async worker** | P (command/event) | P (per-step outcome) | S | P (job lifecycle) | P (plan vs perform) |
| **ML pipeline** | P (chunk/node kinds) | P (per-stage) | P (scores, ids) | S | P (transforms, scoring) |
| **Agent system** | P (tool calls, messages) | P (tool outcomes) | S | P (turn / double-loop) | P (decision logic) |
| **Voice runtime** | P (audio/turn events) | P (hot-path, no exceptions) | S | P (VAD / turn-taking) | S (DSP where latency allows) |
| **CLI tool** | S (subcommand args) | S (exit outcomes) | S | — | S |
| **System script** | S | P (fail with exact cause) | — | — | P (pure logic, thin shell) |
| **Evaluation harness** | P (case outcome) | P (per-case) | P (scores) | S | P (metrics are total functions) |
| **Library** | P (public value types) | P (typed API errors) | P (domain types) | S | P (pure, no hidden I/O) |

## Reading it

- **API service** — request/response and domain events are sum types; ids and validated fields are newtypes parsed at the router (the anti-corruption edge). Result in the service layer where "not found"/"conflict" map cleanly to status codes; exceptions only for true faults.
- **Async worker** — the archetype for this skill. The job is a **command** (data), its lifecycle a **state machine**, each step returns a **Result**, and the *decision* of what to do next is a pure **plan** the shell executes. Serializable commands = replayable, inspectable jobs.
- **ML pipeline** — chunk/node kinds are sum types dispatched per variant; scores and ids are newtypes; every stage returns a Result so a bad document fails one item, not the batch; the transforms are the functional core.
- **Agent system** — tool calls and messages are sum types; tool results are Results; the agent turn / double-loop is a state machine; the reasoning that picks the next action is pure, the tool execution is shell.
- **Voice runtime** — turn/VAD events are sum types; the turn loop is a state machine. **Result over exceptions on the hot path** — raising in a realtime audio loop is a latency and correctness hazard. Keep decisions allocation-light.
- **CLI tool** — lighter. Subcommand arguments as sum types where it clarifies; a clean exit-code outcome as a small Result. Most modeling weight is in the library the CLI drives, not the CLI itself.
- **System script** — Result is the star: the script must **fail with the exact cause**, not a soft story (an identity rule). A thin pure core + a shell that does the I/O keeps even a script testable.
- **Evaluation harness** — metrics are total functions → thick functional core; each case yields a Result and a scored outcome (sum type); scores are newtypes. Determinism is the whole game here.
- **Library** — model the public surface as **value types**: sum types and newtypes as the vocabulary, typed errors as `Result`, zero hidden I/O (that is the caller's shell). A library that leaks stringly-typed data or swallows errors is unusable downstream.

## The through-line

The more a category **decides** (worker, agent, eval, ML), the more it leans on the pure-core + Result + state-machine trio. The more it merely **moves bytes** (a thin API passthrough, a glue script), the more it collapses to parse-at-the-edge + fail-with-cause. In every case the instinct is identical: **turn states, choices and failures into typed values, then let `match` prove you handled them all.**
