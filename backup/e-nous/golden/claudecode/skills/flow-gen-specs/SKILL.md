---
name: flow-gen-specs
description: "Gen: keep specs/tekton/<backend> true to the upstream harness — sources.yml signals, matrix grades, gate order, cron boundary. Use when auditing, updating or extending a backend spec."
metadata:
  family: philosophy
---

# flow-gen-specs

The contract for keeping `specs/tekton/<backend>/*.yaml` — the transpilation models — true to what the upstream harnesses (OpenCode, Claude Code) actually are. The sources of truth are declared in `specs/tekton/<backend>/sources.yml`; the deterministic eye is the `spec/check` node of `op eval run spec`; the gate is the `spec/law` node. This skill carries only the judgement: what a signal means, what it weighs, what may be written and by whom.

## Rules

1. **A spec is data, never code.** An upstream change lands as rows in the affected spec — keys, slots, frontmatter fields, files. `specs/tekton/<backend>/sources.yml` and `core/versioning/matrix.yaml` are also data the run maintains. Only when no row can express a shape does the transpiler grow code, and then the pattern is named before it is improvised. → `references/signals.md`
2. **`sources.yml` is the eye.** Every signal must come from a declared source, in one of the nine categories — identical across backends. If something upstream changes that no source can see, the source row is added first, both backends stay symmetric, and `op eval run spec` proves it.
3. **Deterministic before judgment.** `op eval run spec` first: version, schema-key, index-page and deprecation diffs against the machine's snapshots — zero tokens. A run with no signals ends with a report, not with a read of upstream "just in case". The model only opens what the checker pointed at. → `references/checking.md`
4. **Weight is not invented.** Grade each signal against `core/versioning/matrix.yaml`: a slot that changes takes its grade there, a whole kind appearing is surface, a kind retired or a key that stops answering is contract, prose is cosmetic. Specs never propose a new scale; the ledger grades through the matrix, and a signal the matrix cannot weigh stops the run.
5. **The triple moves together.** `release:` is the docs-snapshot date the spec represents; `verified:` the day the cited source was collated; `status:` the permission — `pending → ready` requires the spec complete and every cited source read the same day, and a run that meets that promotes and says so in its report; a retired entity moves to `obsolete` keeping its file and its note of why. The transpiler reads `ready` and nothing else.
6. **Gate order is the contract.** A spec edit is made by `op enhance run spec` in a sandbox and judged there — the spec contract, a clean render, the grade; then `op transpiler bench` after promotion. `op enhance promote` and `op transpiler apply` stay human. A spec edit that breaks rendering shows up there, not in production.
7. **A scheduled run reports as event.** Touched, signal, proposal, skipped-and-why — idempotent, never wider than its permissions. → `references/scheduling.md`

## Sample

```bash
op eval run spec claudecode --cadence nightly   # 1. the deterministic eye: drift needs or nothing
op enhance run spec --from latest               # 2. speckeeper on those signals, in a sandbox
op reports show                                 # 3. contract, render, grade, verdict, patch
op enhance promote && op transpiler bench       # 4. into specs/, transpiler still replicates
op transpiler plan && op transpiler apply       # 5. the export remains a human act
```

## References

- `references/signals.md` — the classification table: category × signal × grade × the spec row it moves
- `references/checking.md` — the `spec/check` node read mechanically: kinds, snapshots, baselines
- `references/scheduling.md` — the unattended run: `smaintenance`, `speckeeper`, what it must never do
- No `lib.md` — method skill over house code; its tooling (`spec/check`, `spec/law`) is deterministic and named in `references/checking.md`.
