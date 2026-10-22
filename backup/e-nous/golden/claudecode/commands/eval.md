---
description: "Measure a skill's activation with the skill-creator plugin; report only, never edits the corpus."
arguments:
- skill
- queries
argument-hint: "[skill] [queries]"
---

Skill under test: $skill — verify it exists and is canonical under core/tekton/skills/; stop if not.
Queries: $queries

Using the opencode-skill-creator plugin tools when present:
1. skill_validate on the target.
2. skill_eval with runs_per_query ≥ 3 and the given set.
3. Report: trigger rate per query, false negatives, false positives, timing.

This command never modifies the corpus: a proposed description is an
observation returned to the orchestrator for the human to decide. If the
plugin is absent, report the gap — do not simulate the gate.
