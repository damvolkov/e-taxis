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
