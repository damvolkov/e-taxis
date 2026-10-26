# e-taxis

<p align="center">
  <img src="assets/logo.svg" alt="e-taxis" height="110" />
</p>

τάξις, *order of battle*. e-taxis mounts a harness in two halves: the **brain** — an e-nous core (persona,
skills, agents, commands, config, MCP) projected into the harness's tree by the transpiler, from e-nous's own specs — then the **world** that brain
expects — CLIs, MCP servers, plugins, services, env, managed files — in order, verified, undoable. e-nous owns the
content, its schema and its specs; e-taxis owns the code that reads them. The contracts are
[`docs/design.md`](docs/design.md), [`docs/transpile.md`](docs/transpile.md) and [`docs/workflow.md`](docs/workflow.md). P1 (read), P2 (write: user and
machine scopes) and the transpiler (Claude Code, OpenCode, Hermes, OpenHuman) are shipped.

Three houses, one system: **arkhetypo** (e-arkhetypo) is the matter — project blueprints, the stack, the shared core this repo
materializes; **e-nous** is the mind — its two hemispheres, tekton (the engineer) and nomos (the polymath); **e-taxis** is the
joint — it projects one into the other, and grows past transpilation into the deterministic mounting and
maintenance of whole systems. The mark is the word itself in the house square font, on a banner that hugs
it — same glyphs and colors across the family, one deterministic svg per name (`taxis logo`).

One triumvirate, all Greek — the mind decides, the archetypes hold the forms, the order executes:

<p align="center">
  <img src="assets/triumvirate.svg" alt="e-nous · e-arkhetypo · e-taxis" height="230" />
</p>

| Pillar | Is | Changes here |
|---|---|---|
| [e-nous](https://github.com/damvolkov/e-nous) | the mind — persona, skills, agents, commands, workflows, evals, and the transpiler | doctrine |
| [e-arkhetypo](https://github.com/damvolkov/e-arkhetypo) | the archetypes — project blueprints, stacks, CI sources; data only | templates |
| **e-taxis** | the order — the deterministic engine that turns archetypes into running things and installs the mind into each harness | tools |

##### RUN #####

```bash
taxis install --target T --nous PATH [--profile P] [--ref REF | --worktree] [--yes]
              [--accept-licence ID] [--confirm ID] [--json]      # brain, then world: one run, one undo
taxis transpile check|run|reverse|trial …                           # the brain alone: docs/transpile.md
taxis workflow run ID --nous PATH [name=value ...]                  # a corpus workflow, end to end: docs/workflow.md
taxis workflow list --nous PATH · check [ID ...] --nous PATH        # every workflow; its static law
taxis distill guard|intake|index|scan|drift|inventory|grade|report|ship|schemas --rundir DIR [--nous PATH] …
taxis map    [--target T] [--json]                                  # the catalog: targets, scope, rollout per profile
taxis plan   --target T (--profile P | --nous PATH) [--json]    # wanted ⨝ catalog, requires order, probed
taxis verify --target T (--profile P | --nous PATH) [--json]    # every wanted part's verify, all of them
taxis doctor [--json]                                               # schema, ids, requires DAG, primitives, owners
taxis apply  --target T (--profile P | --nous PATH) [--only id,...] [--dry-run] [--yes]
             [--accept-licence ID] [--confirm ID] [--json]              # carry the plan out; dry unless --yes
taxis uninstall ID --target T [--cascade] [--yes]                   # one part (and its dependents) out; dry unless --yes
taxis history list · undo                                           # every run that wrote; revert the last one
```

`T` is `claudecode`, `opencode`, `openhuman` or `system`. `--profile` reads a profile shipped with the catalog
(`house`, `company`, `minimal`); `--nous` reads an e-nous checkout's `core/*/stack.yaml`.

`install`'s brain half is `taxis transpile run --yes` under `~`: the core and specs at the checkout's committed
HEAD (`--ref` another, `--worktree` the tree as it stands), held to the live tree fragment by fragment, with total
ownership — what the spec governs and the core no longer renders is pruned. A target no spec projects (`system`)
has no brain half.

`install`, `apply` and `uninstall` write nothing without `--yes`: they print the plan and exit 0. With it, `apply`
refuses whole before writing when a part is unknown or a gate is closed (`--accept-licence ID`,
`--confirm ID`, the gate's secrets set in the environment), then installs in requires order through one
primitive per recipe (`uv-tool`, `npm`, `binary` with a mandatory sha256, `settings`/`env` on owned keys
only, `file` marked blocks, `claude-mcp`, `claude-plugin`), stops at the first failure and verifies what it
applied. `compose` and the project scope are reported `deferred` (P3). Every change is journaled, even in
a failed run: `taxis history undo` reverts it.

Exit codes: `0` · nothing to undo `4` · catalog does not load `5` · bad source `6` · plan has unknown or
blocked parts `7` · verify failed `8` · doctor found problems `9` · apply refused or failed `10` ·
uninstall failed `11` · transpile `17`–`22` (docs/transpile.md) · nothing to distill `3` · workflow `23`–`26`, lock
held past the wait `75` (docs/workflow.md). The report always prints first.

`TAXIS_CATALOG` points at another catalog root; `TAXIS_TIMEOUT` bounds each probe (seconds, default 10).
`TAXIS_NPM_PREFIX` is where `npm -g` installs (default: npm's own prefix); `TAXIS_DOWNLOAD_TIMEOUT` bounds
a binary download (seconds, default 300); `TAXIS_TEMP` stages downloads (default: the system temp dir).
`CLAUDE_CONFIG_DIR`, when set, is where the world's `~/.claude` paths are written; the brain lands where its spec
says (`~/.claude`).

##### LAYOUT #####

Two branches share one floor. `harness/` mounts a brain and its world onto a machine; `project/` is the
ported arkhetypo engine — registry → plan → scaffold. The materialized sections and the light `ops/`
tooling belong to neither branch.

```
src/e_taxis/cli.py        # the root `taxis` app: GROUPS + CARDS → cyclopts; the branches mount under it

src/e_taxis/harness/      # THE HARNESS BRANCH — mounts a brain + its world onto a live tree
  catalog/                # the data: entries/<id>.yaml (design §3) · profiles/<id>.yaml
  commands/               # catalog (map, doctor) · stack (plan, verify) · install (install, apply, uninstall) · history
  services/               # resolver (join + graphlib DAG) · plan · verify · doctor · apply · uninstall
  models/                 # msgspec contracts: catalog, recipe, profile, stack, wanted, plan, verify,
                          # doctor, primitive, apply, uninstall · ports (the Protocols)
  runtime/                # deps (composition root) · lifespan · settings · source · journal

src/e_taxis/adapters/     # SHARED FLOOR — the project's own adapters (FileCatalog, ShellProbe, ProcessRunner,
                          # WreqDownloader, EffectUndo) beside the materialized e-core service adapters
                          # (base, stores, http…); adapters/primitives/ = one adapter per primitive
src/e_taxis/transpile/    # THE TRANSPILER — e-nous core + specs → each harness, and back (docs/transpile.md)
src/e_taxis/workflow/     # THE WORKFLOWS — e-nous workflow definitions run as graphs of commands and agent sessions,
                          # and reverse-distill's deterministic steps (docs/workflow.md)
src/e_taxis/ops/          # SHARED FLOOR — light tools, standalone via CLI or imported by a branch (logo, registry, file)
src/e_taxis/{core,processors}/  # GENERATED by `make core` from arkhetypo's `projects/python/core` into the package — never edited here
src/e_taxis/project/      # THE PROJECT BRANCH — scaffold a new system from arkhetypo (registry → plan → gen)
tests/unit/               # mirrors src · tests/resources holds the fixture catalogs and e-nous trees
```

##### DEVELOP #####

```bash
make install      # materialize core + sync deps + git hooks
make check        # lint + ty + tach + validate + drift + tests
make cov          # tests under the 100% coverage gate
```
