# agents — the agent entity

An agent is `core/tekton/agents/<id>/{agent.yaml, prompt.md}`; the transpiler emits `agents/<id>.md` per `specs/tekton/<backend>/agent.yaml`. The slot catalog — every slot, its runtimes, its flat projection — lives in `ops/templates/structured/agent.yaml`; read it before inventing anything. This file holds only the operations judgement.

## Create

1. Copy the manifest shape from an existing agent (`scout` is the minimal read-only case; `orchestrator` the maximal delegated one).
2. `persona` + `id` + `description`: the description is the delegation trigger — *when to hand work to this agent*, not a feature list.
3. `mode` and `model`: maintenance and auditor roles run a cheap tier (`model: scout` resolves via config, never a literal provider/model in the manifest); interactive roles inherit.
4. `permission` is deny-first: `"*": deny` then named allows. An unattended agent gets `question: deny`, `edit` limited by path glob to `core/`, and bash as a pattern map (`git log*` allow, everything else denied).
5. `skills_preload` costs tokens on every run — only the role's non-negotiables; everything conditional goes to `skills_ondemand` (one-line triggers; house-only, never exported, but the parser verifies each id exists).

## Update

Edit manifest or prompt in `core/`, re-gate, export. A slot that the flat backend doesn't carry (`persona`, `skills_*`) is `house_only` by design — don't force it into the flat file; the generator injects preload as a `Load first:` line instead.

## Retire

Grep the id across `core/tekton/commands/*/command.yaml` (`agent:`), the orchestrator's `permission.task` map and any workflow before deleting. An agent referenced by a live command transpiles to a dangling delegation at runtime.

## Identity trap

OpenCode identity is the *filename* (`agents/<id>.md`, no `name` frontmatter); Claude Code's is `frontmatter.name`. The transpiler resolves the difference — never hand-write the flat file to fix one.
