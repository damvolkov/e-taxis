# tools — declared kind, pending spec

Tool is instance-shaped in the model (`core/tekton/tools/<id>/`) but has no ready spec (`specs/tekton/opencode/tools.yaml`, `status: pending`; the human survey lives in `specs/tekton/opencode/TOOLS.md`: built-ins + custom + MCP). Today a "tool" in the house is wired through config, not through an entity instance.

## The law while pending

1. **Expose or restrict a tool = config ops**: `core/tekton/config/permissions.yaml` (tool allow/deny per agent, wildcard-first) and `core/tekton/config/mcp.yaml` (servers whose tools the runtime discovers). See `→ flow-gen-lifecycle` rule 1: those modules render to `opencode.jsonc`; nothing here is hand-written there.
2. A **custom tool** as an instance (its own manifest, args schema, flat projection) waits for the spec to reach `status: ready`. Until then, a capability that must exist is either a bash-allowed command in an agent's permission map or an MCP server — real contracts with runtimes, not placeholders.
3. Unblocking follows the research flow (survey upstream tools docs, maintain release/verified in the spec) before any `core/tekton/tools/` dir is created; then this reference becomes craft and gains its own sections.
4. Audit hook for scheduled runs: tools an agent permits but never uses, or MCP servers registered without an explicit four-slot entry in the README plugins section, are findings the run must report.
