# validation — the law, and who runs it

The law is deterministic and blocking; routing and effect are heuristic and cost tokens. Never spend the second on an entity that fails the first. Both run as nodes of the evaluator graphs — `op eval run <kind> <id>` — and again, base against candidate, inside every enhancement.

## The law — deterministic, zero LLM

`ops/evaluator/law/skill.py`, run by the `skill/law` node over a render of your working tree (never the live tree). It enforces the house law over one `skills/<name>/`:

- name matches `^[a-z]+-[a-z]+-[a-z0-9]+$`, scope in `{gen,py,rs,sh,sql,en,es}`, folder == frontmatter `name`;
- description ≤200 chars and carries a `Use when/before` trigger; `metadata.family` present;
- `SKILL.md` ≤60 lines, ≤7 rules, one fenced sample;
- `lib.md` present, or its omission documented (`No \`lib.md\``);
- references are `snake_case`; no reference links another reference.

```bash
op eval run skill <id> --cadence commit   # law, ledgers, needs — zero tokens
op eval ledger <id>                       # the query set and task set parse; cited owners exist
op eval run corpus                        # every validator over the whole corpus, plus the transpiler bench
```

Agents, commands and specs have their own law nodes (`agent/law`, `command/law`, `spec/law`). Third-party skills (`opencode-skill-creator`, `synced/`) are excluded — they don't follow the house law by design.

## Routing and effect — heuristic

The law says the skill is *well-formed*. It cannot say the description *triggers*, nor that the skill *helps*. The evaluator measures both at `--cadence weekly`: `skill/activation` probes routing through the real coder CLI (Wilson interval), `skill/effect` runs the value A/B (no skill against the skill) on the test split. Method → `evaluation.md`.

**OpenCode** — the `opencode-skill-creator` plugin remains useful to iterate a description by hand:

| Tool | Does |
|---|---|
| `skill_optimize_loop` | full activation loop: 60/40 split, 3 samples per query, proposes descriptions, selects on the test score |
| `skill_eval` · `skill_improve_description` | the same two halves, run by hand |
| `skill_validate` · `skill_parse` | structural check against the *plugin's* schema, not the house law — the evaluator's law remains ours |

Pass the model id of the session doing the real work, or the trigger rate measures a model nobody uses.

## Order

Change → **law green** → **routing and effect above threshold** → promote → commit → apply.
