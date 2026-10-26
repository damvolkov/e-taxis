# specs/tekton — Claude Code and OpenCode

How `core/base` + `core/tekton` land in each coder. Data the transpiler reads; one folder per backend, plus
`common/` for what both share. Only `status: ready` specs render.

## Persona — one document, same blocks

| Slot | Heading | Claude Code | OpenCode |
|---|---|---|---|
| `name` · `essence` · `epigraph` | title, lead, quote | `CLAUDE.md` | `AGENTS.md` |
| `origin` | Damien | 〃 | 〃 |
| `unity` | One mind, two materials | 〃 | 〃 |
| `temperament` | Temperament | 〃 | 〃 |
| `face` | The engineer | 〃 | 〃 |
| `stance` · `reasoning` | Philosophy and logic | 〃 | 〃 |
| `voice` · `critique` | Voice | 〃 | 〃 |
| `prudence` · `method` | Method: prudence before action | 〃 | 〃 |
| `honesty` | Honesty | 〃 | 〃 |
| `soul` | Engineering soul | 〃 | 〃 |
| `knowledge` | Knowledge architecture | 〃 | 〃 |
| `categories` | Software categories | 〃 | 〃 |
| `rules` | Skill creation rules | 〃 | 〃 |
| `conduct` · `contract` | Operating contract | 〃 | 〃 |
| `skills` | Skills | 〃 | 〃 |

`about`, `profile` and every nomos slot never reach a coder.

## Entities

| Entity | Claude Code | OpenCode |
|---|---|---|
| skill | `skills/{id}/SKILL.md` (`common/skill.yaml`) | `skills/{id}/SKILL.md` (`common/skill.yaml`) |
| agent | `agents/{id}.md` | `agents/{id}.md` |
| command | `commands/{id}.md` | `commands/{id}.md` |
| workflow | pending | `workflows/{id}.md` |
| tool | obsolete | pending |

## Config — `core/tekton/config`

| Module | Claude Code | OpenCode |
|---|---|---|
| `main` | `settings.json`: `model`, `effortLevel`, `tui`; `rules/instructions.md` | `opencode.jsonc`: `username`, `model`, `small_model`, `instructions` |
| `models` | — (the session alias in `main`) | `opencode.jsonc`: `provider` |
| `agents` | — | `opencode.jsonc`: `agent` |
| `permissions` | `settings.json`: `permissions` | `opencode.jsonc`: `permission` |
| `hooks` | `settings.json`: `hooks`; `hooks/*` scripts | — |
| `plugins` | — | `opencode.jsonc`: `plugin`; `tui.json`; `package.json` |
| `mcp` | user scope (`claude mcp add-json`); `mcp/*` side files | `opencode.jsonc`: `mcp`; `mcp/*` side files |

`settings.json` is shared with Claude Code: the render owns only the keys above. `opencode.jsonc` is generated whole.
Each backend's `sources.yml` is what the spec maintainer watches to keep these maps current.
