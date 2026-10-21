# e-taxis

<img src="assets/etaxis.svg" alt="e-taxis" width="128" height="128" />

τάξις, *order of battle*. e-taxis mounts a harness in two halves: the **brain** — an e-engineer core (persona,
skills, agents, commands, config, MCP) projected into the harness's tree — then the **world** that brain expects —
CLIs, MCP servers, plugins, services, env, managed files — in order, verified, undoable. e-engineer owns the content;
e-taxis owns its contract (`models/core.py`) and every projection of it. The contract is
[`docs/design.md`](docs/design.md). P1 (read), P2 (write: user and machine scopes) and the Claude Code brain are shipped.

Three houses, one system: **e-templates** is the matter — project systems, the stack, the shared core this repo
materializes; **e-engineer** is the mind — the engineer's core and the nomos of the harnesses; **e-taxis** is the
joint — it projects one into the other, and grows past transpilation into the deterministic mounting and
maintenance of whole systems. The mark: the house `e` beside a checker column — τάξις as rank, one square per
verified part.

##### RUN #####

```bash
taxis install --target T --engineer PATH [--profile P] [--ref REF | --worktree] [--yes]
              [--accept-licence ID] [--confirm ID] [--json]      # brain, then world: one run, one undo
taxis brain  --target T --engineer PATH [--ref REF | --worktree] [--yes] [--json]   # the core into the tree
taxis map    [--target T] [--json]                                  # the catalog: targets, scope, rollout per profile
taxis plan   --target T (--profile P | --engineer PATH) [--json]    # wanted ⨝ catalog, requires order, probed
taxis verify --target T (--profile P | --engineer PATH) [--json]    # every wanted part's verify, all of them
taxis doctor [--json]                                               # schema, ids, requires DAG, primitives, owners
taxis apply  --target T (--profile P | --engineer PATH) [--only id,...] [--dry-run] [--yes]
             [--accept-licence ID] [--confirm ID] [--json]              # carry the plan out; dry unless --yes
taxis uninstall ID --target T [--cascade] [--yes]                   # one part (and its dependents) out; dry unless --yes
taxis history list · undo                                           # every run that wrote; revert the last one
```

`T` is `claudecode`, `opencode`, `openhuman` or `system`. `--profile` reads a profile shipped with the catalog
(`house`, `company`, `minimal`); `--engineer` reads an e-engineer checkout's `core/*/stack.yaml`.

`brain` reads the core at the checkout's committed HEAD (`--ref` another, `--worktree` the tree as it stands) and
plans three ways: what the render lands, what the tree holds, what the last install wrote. A file nobody touched
since is an `update`; one edited by hand, or never written by e-taxis, an `overwrite` — shown before it happens.
Owned `settings.json` keys merge beside the harness's own; a document keeps every `## ` section it does not
declare; what a governed folder holds and the core no longer renders is an `orphan`, reported and never removed.
MCP servers register through `claude mcp add-json --scope user`. Only `claudecode` has a projection today.

`install`, `brain`, `apply` and `uninstall` write nothing without `--yes`: they print the plan and exit 0. With it, `apply`
refuses whole before writing when a part is unknown or a gate is closed (`--accept-licence ID`,
`--confirm ID`, the gate's secrets set in the environment), then installs in requires order through one
primitive per recipe (`uv-tool`, `npm`, `binary` with a mandatory sha256, `settings`/`env` on owned keys
only, `file` marked blocks, `claude-mcp`, `claude-plugin`), stops at the first failure and verifies what it
applied. `compose` and the project scope are reported `deferred` (P3). Every change is journaled, even in
a failed run: `taxis history undo` reverts it.

Exit codes: `0` · nothing to undo `4` · catalog does not load `5` · bad source `6` · plan has unknown or
blocked parts `7` · verify failed `8` · doctor found problems `9` · apply refused or failed `10` ·
uninstall failed `11` · core unreadable `13` · brain refused or failed `14`. The report always prints first.

`TAXIS_CATALOG` points at another catalog root; `TAXIS_TIMEOUT` bounds each probe (seconds, default 10).
`TAXIS_NPM_PREFIX` is where `npm -g` installs (default: npm's own prefix); `TAXIS_DOWNLOAD_TIMEOUT` bounds
a binary download (seconds, default 300); `TAXIS_TEMP` stages downloads (default: the system temp dir).
`CLAUDE_CONFIG_DIR`, when set, is where `~/.claude` paths are written.

##### LAYOUT #####

Two branches share one floor. `harness/` is the plane that exists today; `project/` (scaffold from
e-templates) lands next. The materialized sections and the light `ops/` tooling belong to neither branch.

```
src/e_taxis/cli.py        # the root `taxis` app: GROUPS + CARDS → cyclopts; the branches mount under it

src/e_taxis/harness/      # THE HARNESS BRANCH — mounts a brain + its world onto a live tree
  catalog/                # the data: entries/<id>.yaml (design §3) · profiles/<id>.yaml
  commands/               # catalog (map, doctor) · stack (plan, verify) · brain · install (install, apply, uninstall) · history
  services/               # resolver (join + graphlib DAG) · plan · verify · doctor · apply · uninstall · brain
  models/                 # msgspec contracts: core, brain, catalog, recipe, profile, stack, wanted, plan, verify,
                          # doctor, primitive, apply, uninstall · ports (the Protocols)
  runtime/                # deps (composition root) · lifespan · settings · source · journal

src/e_taxis/adapters/     # SHARED FLOOR — the project's own adapters (FileCatalog, GitCore, ShellProbe,
                          # ProcessRunner, WreqDownloader, EffectUndo) beside the materialized e-core service
                          # adapters (base, stores, http…); adapters/harness/ = a projection per harness;
                          # adapters/primitives/ = one adapter per primitive
src/e_taxis/ops/          # SHARED FLOOR — light tools, standalone via CLI or imported by a branch (logo, registry, file)
src/e_taxis/{core,processors}/  # GENERATED by `make core` from e-templates' systems/core into the package — never edited here
src/e_taxis/project/      # THE PROJECT BRANCH — scaffold a new system from e-templates (registry → plan → gen), lands next
tests/unit/               # mirrors src · tests/resources holds the fixture catalogs, e-engineer tree and core
```

##### DEVELOP #####

```bash
make install      # materialize core + sync deps + git hooks
make check        # lint + ty + tach + validate + drift + tests
make cov          # tests under the 100% coverage gate
```
