# config — the singular modular configuration

Config is one entity rendered from many modules: `core/tekton/config/{main,models,agents,permissions,mcp,plugins}.yaml` → `opencode.jsonc`, `tui.json`, `package.json`, built per `specs/tekton/opencode/config.yaml`. The artifacts are byte-exact generated JSON with a canonical key order and no prose — comments live in `core/tekton/config`.

## Update

1. Never hand-edit the exported `opencode.jsonc` / `tui.json` / `package.json`. An emitted key that is not declared in the spec's `keys` list is an error — the fix is the module or the spec, not the artifact.
2. New provider, model tier, plugin, MCP server → **a row in the right module, never code**: providers/tiers in `models.yaml` (agents cite the tier name, e.g. `model: scout`, resolved at render), plugins in `plugins.yaml` with explicit registration — accidental discovery is not installation (the four slots per plugin: what / install / config / verify).
3. `instructions` points at composed memory, `permission` at wildcard rules; visibility-per-agent changes here, content changes in the entities.
4. Gate: `op transpiler plan` then `op transpiler apply` — the export lands in each coder's canonical dir (`opencode.jsonc` in `~/.config/opencode`, `settings.json` in `~/.claude`), so config drift is drift of the coder itself, not just of a file.

## Retire

Removing a plugin = remove the registration row, drop its config/data/cache paths as the README's uninstall slot says, export, verify absence in `tui.json`/`opencode.jsonc`. A plugin left registered-but-deleted is the failure mode: it loads from cache and reports alive.
