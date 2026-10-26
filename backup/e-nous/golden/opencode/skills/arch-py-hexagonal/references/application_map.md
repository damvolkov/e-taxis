# Application map — macro structure per software category

For each of the nine software categories (→ `AGENTS.md`), how much of the hexagonal shape earns its place. `P` = primary (build it this way by default) · `S` = secondary (when it grows / when a second adapter appears) · `—` = usually not worth it.

| Category | Ports & Adapters | Dependency Injection | Repository | Pipeline (handlers) | Composition root |
|---|---|---|---|---|---|
| **API service** | P | P | P | P (middleware) | P |
| **Async worker** | P | P | S | P (processor chain) | P |
| **ML pipeline** | P | P | P (vector/doc store) | P (ingest→embed→index) | P |
| **Agent system** | P | P | S (memory store) | S (tool/step chain) | P |
| **Voice runtime** | P | P | — | P (audio→stt→…→tts) | P |
| **CLI tool** | S | S | — | — | P (registry of commands) |
| **System script** | — | — | — | — | S (just `main`) |
| **Evaluation harness** | S | S | S (case store) | P (run→score→report) | P |
| **Library** | P (public Protocols) | P (inject, never construct) | — | — | — (the caller wires) |

## Reading it

- **API service** — the full shape. Driving adapters = routers; driven adapters = stores/clients; middleware for cross-cutting; DI via the framework at the root. The reference implementation of hexagonal.
- **Async worker** — driving adapter = the queue consumer; the job body is a processor chain over the payload; DI at worker startup. Repository only if the job owns domain state.
- **ML pipeline** — ports for every model/index; the pipeline *is* the processor chain; repository for the vector/doc store. Anti-corruption matters most here (vendor SDKs churn).
- **Agent system** — LLM, tools and MCP servers are all driven ports; the orchestrator is the core. Tools plug in as adapters; a memory store is a repository when memory has identity.
- **Voice runtime** — STT/TTS/VAD are driven ports (swap Whisper/Piper freely); the turn loop is the core; the audio path is a streaming processor chain. No repository — state is ephemeral. Latency budget: keep the core allocation-light.
- **CLI tool** — DI is light (construct at the root); the real value is the **command registry** (explicit registration) and a facade over the domain. Ports appear only where the CLI drives real infrastructure.
- **System script** — resist the shape. A pure function taking its inputs is already the core; call the real dependency directly. Add a port only when a second implementation (a test fake) is needed.
- **Evaluation harness** — the pipeline (run → score → report) is primary; ports for the system-under-test so you can swap models/providers; a case store when the corpus has identity. Determinism over cleverness.
- **Library** — expose **Protocols**, not concrete classes, as the public surface; accept dependencies, never construct them internally — the *caller* is the composition root. A library that news-up its own I/O is unusable in someone else's hexagon.

## The through-line

The more an artifact **lives** (a server, a worker, an agent), the more of the shape it needs. The more it is a **one-shot** (a script), the less. The dividing question is always the same: *will a second implementation of this dependency ever exist — including a test double?* If yes, it is a port. If no, call it directly and move on.
