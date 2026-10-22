# specs/nomos — OpenHuman and Hermes

How `core/base` + `core/nomos` land in each nomos backend. Data the transpiler reads; one folder per backend. The core is
agnostic; each `config.yaml` translates it, and its `native` block holds what only that harness has.

## Persona

| Slot | OpenHuman | Hermes |
|---|---|---|
| `name` · `essence` · `epigraph` | `SOUL.md` title, lead, quote | `SOUL.md` title, lead, quote |
| `temperament` · `face` · `critique` | `SOUL.md` Personality | `SOUL.md` Personality |
| `about` | `SOUL.md` About You | `SOUL.md` About You |
| `family` | `SOUL.md` Family | `SOUL.md` Family |
| `attunement` | `SOUL.md` Attunement | `SOUL.md` Attunement |
| `unity` | `SOUL.md` One mind, two materials | `SOUL.md` One mind, two materials |
| `stance` | `SOUL.md` Outlook | `SOUL.md` Outlook |
| `worldview` | `SOUL.md` Worldview | `SOUL.md` Worldview |
| `lineage` | `SOUL.md` Lineage | `SOUL.md` Lineage |
| `taste` | `SOUL.md` Taste | `SOUL.md` Taste |
| `mission` | `IDENTITY.md` Mission | `SOUL.md` Mission |
| `nature` | `IDENTITY.md` Nature | `SOUL.md` Nature |
| `honesty` | `IDENTITY.md` Honesty | `SOUL.md` Honesty |
| `reasoning` · `epistemics` | `IDENTITY.md` Epistemics | `SOUL.md` Epistemics |
| `memory` | `IDENTITY.md` Memory | `SOUL.md` Memory |
| `commitments` | `IDENTITY.md` Commitments | `SOUL.md` Commitments |
| `antagonists` | `IDENTITY.md` Antagonists | `SOUL.md` Antagonists |
| `limits` | `IDENTITY.md` Limits | `SOUL.md` Limits |
| `voice` · `discourse` | `STYLE.md` | `SOUL.md` Voice |
| `prudence` | `ROLE.md` Method | `workspace/AGENTS.md` Method |
| `modes` | `ROLE.md` Modes | `workspace/AGENTS.md` Modes |
| `conduct` | `AGENTS.md` Conduct | `workspace/AGENTS.md` Conduct |
| `lexicon` | `AGENTS.md` Lexicon | `workspace/AGENTS.md` Lexicon |
| `craft` | `AGENTS.md` Craft | `workspace/AGENTS.md` Craft |
| `profile` | `PROFILE.md` (seed) | `memories/USER.md` (seed) |

OpenHuman's persona lives in `~/.config/memory/persona` (its workspace links there) and `AGENTS.md` in its workspace;
Hermes's in `HERMES_HOME`, `AGENTS.md` in the working directory `config.yaml` pins. Seeds — `PROFILE.md`,
`memories/USER.md` — carry the minimum: the harness grows them, and what it adds is its region, never absorbed.
Memory files (`MEMORY.md`) are never written: each harness curates its own.

## Config — `core/nomos/config`

| Module | OpenHuman (`config.toml`) | Hermes (`config.yaml` · `.env`) |
|---|---|---|
| `main` | `agent.agents_md_enabled` | `timezone` |
| `models` · providers | `cloud_providers` (`native.ids`, plus its own backend) · `primary_cloud` | `providers.<native.names>` (`base_url`, `api_mode`, `key_env`) |
| `models` · roles | `default_model`, `<role>_provider`, `memory_tree.smart_walk_model` (`native.roles`) | `model`, `auxiliary.<task>`, `delegation` (`native.auxiliary`) |
| `models` · fallback | — | `fallback_providers` |
| `memory` | `memory.*`, `custom_embeddings`, `agent.memory_window` | — |
| `sources` | `memory_sources` (folders; connectors are the app's) | — |
| `search` | `search.roles`, `search.providers` (`native.routes`), `searxng.base_url` | `web.search_backend` · `SEARXNG_URL` |
| `tools` | `agent.*`, `context.*`, `http_request.*`, `curl.*`, `search.*`, `multimodal*.*` | `agent.max_turns`, `terminal.timeout`, `tool_output.max_bytes` |
| `permissions` | `autonomy.enabled`, `autonomy.level` (`native.levels`), `autonomy.workspace_only` | `approvals.mode` (`native.levels`) |
| `channels` | `channels_config.discord.*` (only once the app connected it) | `discord.*` · `DISCORD_ALLOWED_USERS` |
| `mcp` | — | `mcp_servers.*` |
| `voice` | `stt_provider`, `tts_provider`, `voice_providers`, `local_ai.*` | — |

A dash is a knob the harness does not have today; `TODO.md` tracks each gap. Secrets are never rendered: the core
names the variable, the harness keeps the value.
