# scheduling — unattended maintenance

The corpus must survive its operator's absence. Unattended, the system **measures and proposes**; the human **promotes and applies**. Same contract as interactive operation, different failure model: nobody reads a question at 04:00.

## What runs

- **Timers** (`make timers`, systemd user units): `ops-eval@<target>-<cadence>` runs `op eval run <target> --cadence <c>`, then `op enhance run <target> --from latest`. The enhancer acts only on the needs that evaluation recorded; with none, it records `nothing to enhance` and stops.
- **Workflows**: `emaintenance` (one entity: create/retire by hand-craft, update through the enhancer) and `smaintenance` (specs drift → speckeeper). Both run from `op workflow run <id> k=v…` or from a coder with `/workflow <id>`; their `publish` parameter is the human's authorization, empty by default.
- **gh-aw**: a trigger that runs the zero-token graphs and opens an issue with the reports.

## The run

1. **Evaluate first, always**: a green subject with no needs is the best run — the enhancer skips it.
2. **Act in the sandbox**: every edit — integrator, speckeeper, SkillOpt's lessons — lands in `.reports/<run>/sandbox`; the verdict and the patch are the proposal.
3. **Idempotence**: re-running on the same state yields the same needs and no new proposal beyond the ledger.
4. **Report as event**: every run leaves `command.json`, `ledger.jsonl` and `report.md`; `op reports list` shows them. Silence is a failure mode: a run that found nothing says so.

## What scheduled runs must never do

Run `op enhance promote`, `op transpiler apply` or `restore`; enhance without a recorded need; delete an entity; widen an agent's permissions to get a gate green. A maintenance process that edits its own contract has stopped being maintenance.
