# transpile — work log

Every step of the transpiler rebuild, in order, for later audit: what was done, the evidence, what was decided
without the owner and why, and what stays open. Newest last. Design: [`transpile.md`](transpile.md).

## 2026-10-26 · T0 — schemas compiled on the fly, `transpile check`

**Done.** `transpile/engine/schema.py` parses the type grammar of `core/schema.yaml` and `specs/base.yaml` into an
AST and compiles it to closed msgspec types (`defstruct`, `forbid_unknown_fields`); the same AST yields leaf paths.
`CoreModel` and `SpecModel` compile the two schemas; `GitNous` reads core and specs at one ref (or the worktree)
with `{source}` envelopes resolved and confined; `SpecLaw` holds each spec to the invariants of `base.yaml`;
`CheckService` + `taxis transpile check` report, stamped with commit and spec versions.

**Evidence.** 404 unit tests, coverage 100 % (taxis's gate); 15 seeded mutations, each caught as its own kind;
`taxis transpile check --nous e-nous --worktree` → 0 blocking · 3 signal; against e-nous HEAD before PR #83 it
failed with exit 20 on the prose `Via` shape, as it should.

**Decided alone.**
- Envelopes `{source}` are resolved by the reader, so the compiler drops them from unions: msgspec refuses two
  untagged structs in one union (`list<Node | {source: path}>`).
- Map keys in the grammar are documentation (`map<slot, Text>`): keys are always strings.
- `backend` is declared as `str`, not an enum: the schema must not enumerate backends (a new one is a new file).
- `CoreModel` compiles one namespace per facet: `McpServer` differs between tekton and nomos.
- `compile` dispatches on the AST variant through a frozen mapping (house dispatch law), not a seven-arm match.
- Unused accessors of `CoreModel` were cut rather than tested: no speculative surface.

**Found in e-nous and fixed** (PR #83, merged): `Via.shape` was prose; `entity`, `probe`, `name`, `backend` were used
as types and declared nowhere; workflow `parameters` also take `{doc, type}`; an unquoted label in
`nomos/config/models.yaml` split at its comma into a phantom key; `report.kinds` lacked the check kinds.

**Mistakes, corrected.** Creating the test resource I deleted the existing `tests/resources/nous` (used by the
stack tests) without looking; restored from git, the new resource lives in `tests/resources/transpile`.

**Open.** e-serde 0.5.1 dumps a list of lists as YAML it cannot read back (`-     - a`): the test fixture writes
with PyYAML; the transpiler's YAML target (Hermes `config.yaml`) needs it fixed or worked around (T5).

## 2026-10-26 · T1 — the row engine, `transpile run --out`

**Done.** A render is a list of `Placement`s (target, fragment, value, and its provenance: section, row, core
paths) — the intermediate form a report and a reverse walk back. `engine/render.py` (`SpecRender`) turns the rows
of one spec into placements: persona slots, each instance's fields (sorted by id), config paths, `native.`, constants;
`via` runs left to right through `engine/combinators.py` (the 18 of the model, a closed table) and the backend's
named transforms (`transforms/<backend>.py`, a table per backend, `transforms/catalog.py`); `each` fans a mapping
out; `#copy` copies an instance's files; config `assets` travel as bytes. `engine/encode.py` groups placements per
target and encodes them by format (`codecs/`: Markdown typeset, md+frontmatter, JSON, text, file); `registry` and
`link` targets yield entries and links, never files. `RunService` refuses a checkout its own law refuses, then writes
a pure export; `taxis transpile run --target T --nous P --out DIR`.

**Evidence.** 476 unit tests, coverage 100 %. Against the real e-nous at HEAD: claudecode 202 files byte-identical
to the v1 golden, opencode 205. Every difference is named: `settings.json` (total ownership: `env`,
`enabledPlugins`, two pinned flags, key order), `opencode.jsonc` and `hooks/cbm-session-reminder` and
`mcp/codegraph.md` (PR #81: Serena pin, tree-sitter and the reminder hook out, codegraph guide), `workflows/
reverse-distill.md` (schemas moved beside the workflow), two flow-gen-lifecycle references (the catalog path is now
`core/schema.yaml`). An acceptance test holds the fixture's render to the golden byte for byte.

**Decided alone.**
- The IR is the flat list of placements, not a tree of documents: grouping by target is a projection of it, and
  provenance rides on every fragment for free.
- `transpile run` without `--out` refuses until T3 (the live path needs ownership and the journal).
- Transforms are injected into the engine by backend, never imported by it: the engine names no backend.
- `agents_registry` refuses a name present in both overrides and system agents (v1 let system silently win).
- A row with neither `from` nor `value` is now a law finding (`invalid`), with its seeded mutation.

**Found and fixed in e-nous** (PR #84, merged): a bulk rename in #82 had left a non-existent
`ops/core/schema.yaml` in two flow-gen-lifecycle references — the render diff against the golden caught it.

**Mistakes, corrected.** `ruff format` over `tests/` rewrote code fences inside the fixture's Markdown (the house
law: ruff never formats Markdown). The golden acceptance test caught it; the fixture was resynced from e-nous and
`tests/resources` is now excluded from ruff.
