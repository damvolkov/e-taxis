# agent — double-loop / semi-deterministic graph

The agentic runtime: an inner loop that acts and an outer loop that supervises, tools it can call, and adapters to the world. Modeled on `e-heed`/`e-clawhisper` (daemon) and `e-agents` (rtc).

```
src/e_<name>/
├── cli/                  # commands/ — run, config, session (operate the daemon)
├── shared/               # core, helpers, adapters, operational — cross-loop infra
└── daemon/               # (or rtc/) the agent core
    ├── turn/             # the inner loop: one turn = perceive → decide → act
    ├── sentinel/         # the outer loop: supervise, interrupt, guard the turn
    ├── tools/            # function tools the agent may call
    ├── config/           # mcps/ — MCP server configs (explicit registry)
    ├── models/           # turn state, message, tool-call as typed values
    └── adapters/         # agent/ (LLM), stt/, tts/, ww/ — the world
```

## Non-negotiables

- **Double loop** — `turn/` decides and acts; `sentinel/` watches and can interrupt or replan. Keep them separate: the inner loop is fast and dumb, the outer is slow and wise.
- **State as typed values** — turn state, messages and tool-calls are sum types → `arch-py-adt`; the flow between components is events → `arch-py-events`. "Semi-deterministic" means the graph of states is explicit; only the LLM step is stochastic.
- **Tools are registered, not decorated** — a tool is a plain function added to a registry; MCP servers are declared in `config/mcps/`, wired at the root → `arch-py-hexagonal`.
- **Adapters swap the model** — `adapters/agent/` hides the LLM client behind a port; STT/TTS/WW as in voice. The LLM/agent stack lives in the `agent`/`ml` families' `lib.md`, not here.
- **Operated by a CLI** — `cli/commands/` runs, inspects and configures the daemon → `cli.md`.
- **Interruptibility** — cancellation propagates through the turn; nothing orphaned → `conc-py-async` · `lang-py-lifecycle`.
