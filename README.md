<p align="center">
  <img src="assets/logo.svg" alt="e-taxis" width="220" />
</p>

# e-taxis

τάξις, *order of battle*. e-taxis mounts a harness in two halves: the **brain** — an e-engineer core (persona,
skills, agents, commands, config, MCP) projected into the harness's tree — then the **world** that brain expects —
CLIs, MCP servers, plugins, services, env, managed files — in order, verified, undoable. e-engineer owns the content;
e-taxis owns its contract (`models/core.py`) and every projection of it. The contract is
[`docs/design.md`](docs/design.md). P1 (read), P2 (write: user and machine scopes) and the Claude Code brain are shipped.

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

```
src/e_taxis/catalog/      # the data: entries/<id>.yaml (design §3) · profiles/<id>.yaml
src/e_taxis/cli.py        # GROUPS + CARDS → the cyclopts tree; nothing under commands/ loads until it runs
src/e_taxis/commands/     # catalog (map, doctor) · stack (plan, verify) · brain · install (install, apply,
                          # uninstall) · history
src/e_taxis/services/     # resolver (join + graphlib DAG) · plan · verify · doctor · apply · uninstall · brain
src/e_taxis/adapters/     # ports · FileCatalog · sources · GitCore · ShellProbe · ProcessRunner · WreqDownloader ·
                          # EffectUndo
src/e_taxis/adapters/harness/     # one projection per harness: claudecode
src/e_taxis/adapters/primitives/  # one adapter per primitive: binary, uv, npm, settings, file, mcp, plugin, compose
src/e_taxis/runtime/      # launcher · lifespan · deps (the composition root) · settings · source · journal
src/e_taxis/models/       # msgspec: core (the content contract), brain, catalog, recipe, profile, stack, wanted,
                          # plan, verify, doctor, primitive, apply, uninstall, journal, errors
src/core/ src/ops/ src/adapters/   # GENERATED by `make core` from e-templates — never edited here
tests/unit/               # mirrors src · tests/resources holds the fixture catalogs, e-engineer tree and core
```

##### DEVELOP #####

```bash
make install      # materialize core + sync deps + git hooks
make check        # lint + ty + tach + validate + drift + tests
make cov          # tests under the 100% coverage gate
```
