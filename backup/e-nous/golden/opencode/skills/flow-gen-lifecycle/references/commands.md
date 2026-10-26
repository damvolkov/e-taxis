# commands — the command entity

A command is `core/tekton/commands/<id>/{command.yaml, template.md}`; the transpiler emits `commands/<id>.md` per `specs/tekton/<backend>/command.yaml` — the filename *is* the `/command`. The slot catalog lives in `ops/templates/structured/command.yaml`. This file holds only the operations judgement.

## Create

1. A command is a *named workflow entry point*: one repeatable flow an operator triggers. If it's pure judgment with no fixed steps, it's a skill, not a command.
2. `inputs` are the contract: declare named args in order with a one-line description each; the template body then speaks `{{nombre}}`/`$nombre`. Positional `$1` markers in a canonical body are a transpilation smell — the generator maps order for OpenCode.
3. `agent` must exist in `core/tekton/agents/` (the parser verifies). Decide whether the command *is* the flow (`subtask: false`, current agent) or *delegates* it (`agent: builder/orchestrator`, `subtask: true`).
4. `skills.preload` / `skills.ondemand` wire the judgment the command depends on — same rule as agents: preload is paid on every run.
5. `template.md` holds the prompt: steps, gates to run, what to report. It routes to skills by name (`→ skill-name` or a "Load `x` first" line); it never re-states their content.

## Update / retire

Source-only edit, gate, export. Before deleting: grep the id (`/name`) across `core/`, `specs/` and docs — commands are referenced by name from chat, workflows and other templates. Claude's modern representation folds commands into skill-directories; the backend drift is spec-owned, not yours.
