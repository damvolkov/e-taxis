---
description: "Deterministic ecosystem check: flat↔structured sync, agents, commands and skill-law validators."
---

Run the corpus evaluation; fix nothing silently.

!`uv run op eval run corpus 2>&1 | tail -3`

Read the report it names (`uv run op reports show latest`) and report per node: status and violations.
If a node fails: stop — core/ is the source of truth; a live tree that lags core/ is brought in
line with `op transpiler plan` then `op transpiler apply`, and no semantic edit happens without
the owner's decision.
