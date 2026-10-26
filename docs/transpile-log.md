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

## 2026-10-26 · S1 — the sandbox: fence, fake model, phantom harnesses

**Done.** `adapters/fence.py` (`LandrunFence`): every trial process under Landlock — read and execute `/`, write
only the sandbox root, TCP only to the fake model's port, `env -i` so nothing is inherited, the whole process group
killed at its limit; `canary` proves the fence holds (a write inside lands, one outside is refused) before any
harness runs. `adapters/capture.py` (`HttpCapture`): a fake model endpoint on a kernel-chosen loopback port that
keeps every request body and answers a final 400. `services/trial.py` (`TrialService`): a fresh sandbox, the core
projected into `<home>/<tree>`, the spec's `trial` state planted, every probe run fenced; evidence is derived from
the render (every non-empty persona text, every instance id) and checked, whitespace folded, in what the harness sent
or printed. `taxis transpile trial --target T --nous P` exits 22 when the phantom did not show everything.

**Evidence.** 497 unit tests (fakes for fence and capture; a stand-in landrun runs the real adapter in CI), coverage
100 %. Real, fenced, on the full e-nous: Claude Code 2.1.310 shows persona 22/22, skills 31/31, agents 14/14; OpenCode
1.19.4 persona 22/22, skills 31/31, agents 14/14, commands 7/7. `tests/e2e` (marked slow, never in CI) runs the canary
and both harnesses on the fixture and fingerprints the live files under the real HOME around the session: no leak.
Run it with `TAXIS_E2E_PATH=<dir of a stable opencode> uv run pytest tests/e2e -m slow --no-cov`.

**Decided alone.**
- The trial lives in `src/` (adapter + service + command), not only in tests: the evaluators (MCP loading, routing)
  need the same sandbox.
- `timeout` parameters are named `limit` (the async lint's rule); served probes, overlays and setup refuse until the
  nomos backends need them (T5).
- The Makefile is materialized from arkhetypo: no `e2e` target added here; the command is documented above.

**Found and fixed in e-nous** (PR #85, merged): the opencode trial never reached its model — the render's
`enabled_providers` hid the ghost provider (`ProviderModelNotFoundError`). Upstream re-read: 1.19.4.

**Open — the owner's decision.** The OpenCode on this machine is **2.0.28, a prerelease line** (`~/.opencode/bin`,
not the npm/GitHub stable channel the spec watches, which is at 1.19.4). 2.x drops `--pure` and `debug skill`, so the
spec's trial cannot run there, and the spec's rows were never checked against 2.x: either pin the stable release on
this machine, or move `specs/tekton/opencode.yaml` (channel, rows, trial) to 2.x.

## 2026-10-26 · T2–T3 — total ownership, the plan, the landing through the journal

**Done.** Each codec now reads live bytes back into the fragments the render compares (`split_*` / `read_*`:
Markdown blocks, frontmatter keys + title + preload + body, dotted JSON keys and the unowned "strays").
`engine/plan.py` holds a projection against the live tree, fragment by fragment: `missing`, `drift`, `stale` (an
unowned key or block, or a file in a governed directory no row renders), `symlink`; the registry entry by entry;
`land_plan` carries a target's foreign parts (marker regions, foreign keys) over the render. `LandService` plans and
lands: atomic writes (a link becomes a real file), stale governed files removed, the registry synced through the
spec's `apply.add`/`apply.remove` with HOME pinned and CLAUDE_CONFIG_DIR unset; every change is a journal effect
(`taxis history undo`), then the landing is recorded (`transpile:<backend>`: commit, spec, digests) as the base of
the three-way reverse. `taxis transpile run --target T --nous P [--home H]` plans; `--yes` lands; `--out` still exports.
The report gained the row and the core paths of every finding, and a count per kind.

**Evidence.** 516 unit tests, coverage 100 %, stable over three runs. e2e (`tests/e2e/test_land.py`, real files and
Claude's real `claude mcp` in a sandboxed HOME): a landing, then an empty second plan (idempotence), then every effect
undone newest first → no file of ours left, no registration. Plan (read-only) against the real trees:
- `~/.claude`: 3 drift (two flow-gen-lifecycle references #84 fixed; settings.json key order only), 1 stale
  (`hooks/cbm-session-reminder`, retired in #81), 1 missing (`e-gnosis` is no longer in the live registry).
- `~/.config/opencode`: the same two references, `workflows/reverse-distill.md` (moved schemas), and **6 sections
  of `AGENTS.md` no row renders** (see Open).

**Decided alone.**
- Nothing was landed on the real trees: changing the owner's live environment waits for the owner.
- Live JSON is read with msgspec (key order kept); JSONC only when the file holds comments, and then its strays are
  sorted — e-serde decodes JSONC in a key order that changes between processes (bug, see Open).
- An empty or unreadable frontmatter reads as "no keys": every owned key then shows as drift instead of crashing.
- `timeout`-style and positional-heavy signatures were made keyword-only (lint), no behaviour change.

**Found and fixed in e-nous** (PR #86, merged): `skills/.trash` is Claude Code's own trash — the plan reported its
9 files stale, and a landing would have pruned them. Declared foreign.

**Open — the owner's decisions.**
1. `~/.config/opencode/AGENTS.md` holds six `##` sections no row renders (Agent Rules, Tool Usage, Config
   Management, File Structure, Communication Preferences, Error Handling — the text of `~/AGENTS.md`). v1 kept
   undeclared headings; under total ownership v2 prunes them on landing. They need a home in the core (a slot, or a
   foreign heading in the opencode spec) before the first landing.
2. e-serde 0.5.1, second bug: JSONC decode does not keep key order (a different order per process). Worked around.

## 2026-10-26 · T4 — `transpile reverse`, three points per fragment

**Done.** A landing now records a digest per rendered fragment (`fragments` in `transpile:<backend>`).
`engine/reverse.py` reads each target back against the render and that base: live = render → settled; live = base →
the core moved (`transpile run --yes` lands it); render = base → **the harness moved** (`harness` kind), with why it can
or cannot fold back — absorbable into its core path when one invertible row owns the fragment on a target that
`absorb`s; held when one block carries several slots, when the row transforms its value, or when the target does not
absorb; "added by the harness" when no row renders it; all three apart → both moved. No landing recorded → plain drift.
`taxis transpile reverse --target T --nous P [--home H]` reports; it writes nothing, the core included.

**Evidence.** 524 unit tests, coverage 100 %: a fresh landing reads settled; seeded edits are each told apart (a
single-slot section → absorbable into `honesty`; the two-slot `Voice` block → held; a new `## Mine` → added by the
harness; `settings.json#effortLevel` → the target does not absorb; a core-only edit → the core moved; core and harness
on one block → both moved; no base → drift; a deleted file → missing). Against the real trees (never landed by v2):
every difference reads as drift without a base, as it should.

**Decided alone.**
- Report only, as agreed: writing absorbed values back into `core/` is the next step and needs the owner's go.
- A harness edit inside a multi-slot block is held, not split: splitting by spans (v1's `Typeset.split`) is the
  part of `--write` that decides which slot owns an edit, and it belongs with it.
- No e2e for reverse: a real harness cannot be made to edit its files offline; the deterministic seeds above stand in.
