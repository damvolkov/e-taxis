---
name: flow-gen-lifecycle
description: "Gen: CRUD lifecycle of every corpus entity — skills, agents, commands, workflows, tools, persona, config: core/ source, gates then export, cron-safe. Use when creating, updating or retiring an entity."
metadata:
  family: philosophy
---

# flow-gen-lifecycle

The contract for operating on the corpus itself — create, update, retire any of its seven entity kinds (skills, agents, commands, workflows, tools, persona, config) under one source, one gate order, one export. The law lives in `README.md` + `TEMPLATE.md`; the mechanics in `ops/`; this skill carries only the judgement and the invariants.

## Rules

1. **One source: `core/`.** Entities are born and die in `core/tekton/skills/`, `core/tekton/agents/`, `core/tekton/commands/`, `core/tekton/workflows/`, `core/tekton/tools/` — and in the two singulars, `core/base/` (persona) and `core/tekton/config/`; the exported trees (`~/.config/opencode`, `~/.claude`) are artifacts — hand-editing it is lost on the next apply and turns `op transpiler plan` into *would lose work*. Every change lands through the transpiler.
2. **An entity is manifest + body, or a singular source.** Instance kinds: a structured `<id>/` folder — `{skill,agent,command,workflow,tool}.yaml` with `{source: ...}` slots pointing at its prose. Persona and config render singly, by document/config spec. `specs/tekton/<backend>/<entity>.yaml` is what the flat file will look like — read it before inventing a slot, and never create instances of a kind whose spec is not `status: ready`.
3. **Create by the law of the kind.** Domain from the catalog, budgets before content, one sample last. Craft per kind → `references/<kind>.md` — the seven are under References.
4. **Evaluate, then enhance on a reason.** `op eval run <kind> <id>` measures and states needs (deterministic, then heuristic at the weekly cadence); `op enhance run` acts only on those needs, your `--directive` or your `--manual` edits, in a sandbox, and ends in a verdict and a patch. Never spend a model call on a red structure. → `references/evaluation.md`
5. **Retire by reference first.** Grep the id across `core/`, `specs/` and `ops/evaluator/ledgers/queries/` — every `→ skill-name` pointer, `skills:` preload and query owner dies with it — then delete the source, apply with `--capability reset`, and verify absence with `op transpiler check`.
6. **Automation evaluates and proposes; you promote and apply.** Timers and workflows run `op eval run` and `op enhance run --from latest`; `op enhance promote` and `op transpiler apply` are human. Persona and config are human-owned end to end. → `references/scheduling.md`
7. **Mechanics are not skill.** `op` — transpiler, evaluator, enhancer, workflows — is deterministic code in `ops/`; `make` only builds the repo. Where a command answers the question, the skill states the invariant and routes — it re-derives nothing.

## Sample

```bash
# update a skill and publish it — the same flow for any entity kind
op eval run skill para-py-dispatch --cadence weekly                           # 1. measure: needs
op enhance run skill para-py-dispatch --from latest --directive "…"           # 2. act on a reason, in a sandbox
op reports show                                                               # 3. verdict, evidence, patch
op enhance promote --ids para-py-dispatch && git commit                       # 4. into core/
op transpiler plan && op transpiler apply --note run:<id>                     # 5. back up, export, record
```

Deterministic nodes are free; heuristic and semantic ones cost tokens; the apply is reversible through `op transpiler log`/`restore` — order them that way and no step is ever scary.

## References

- `references/skills.md` — authoring a skill end to end: domain model → name → router → references → lib.md → staging of auto-generated candidates
- `references/agents.md` — the agent entity: manifest slots, model tiers, permission and visibility, prompt source
- `references/commands.md` — the command entity: inputs, owning agent, skill preload/on-demand, template source
- `references/workflows.md` — the graph kind: how to draw a DAG, what the node contract is, how a bounded `loop:` unrolls into copies
- `references/tools.md` — the kind still pending spec: what must not be created yet
- `references/persona.md` — the singular identity document: sections → `AGENTS.md`, tier-1 cost, human-owned
- `references/config.md` — the singular modular config: rows in modules, never code, never the rendered jsonc
- `references/validation.md` — the deterministic law and its runners: the evaluator graphs and `opencode-skill-creator`
- `references/evaluation.md` — the stochastic questions: activation (60/40, near-miss negatives) and effect (paired baseline, discrimination matrix)
- `references/scheduling.md` — unattended maintenance: timers, `emaintenance`/`smaintenance`, what automation never does
- No `lib.md` — method skill over house code; its tooling (`op`, the transpiler, the validators) is deterministic and named in `references/validation.md`.
