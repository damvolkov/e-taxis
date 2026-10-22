---
description: "Author a house skill end to end with the saved flow: law naming, router, references, gates, eval."
arguments:
- need
argument-hint: "[need]"
---

Load `flow-gen-lifecycle` first; follow its pipeline end to end.
Need: $need

1. Model the domain: the single decision it governs and the user trigger.
2. Name by the law: <domain>-<scope>-<topic>, folder == frontmatter name.
3. Copy TEMPLATE.md; keep SKILL.md a router: ≤60 lines, ≤7 rules, one sample;
   description ≤200 with the form "<Scope>: <what>. Use when <trigger>.".
4. Push depth to references/<snake_case>.md; write lib.md or document its absence.
5. Gate: `uv run op eval run skill <name> --cadence commit` — law green, needs read.
6. Eval activation with the opencode-skill-creator tools if available; iterate
   the description until it passes; never ship a description untested.
7. Publish: commit, then `op transpiler plan` and `op transpiler apply` — plan, back up, transpile, record.
8. Deliver: path, name, gate result, eval result. No "done" without evidence.

The saved flow is still being tuned: if any step contradicts README.md law,
the law wins and you report the contradiction — do not silently patch the skill.
