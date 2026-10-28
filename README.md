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

The Triad, all Greek — the will decides (e-nous), the body holds the forms (e-arkhetypo), the hand executes (e-taxis):

<p align="center">
  <img src="assets/triumvirate.svg" alt="e-nous · e-arkhetypo · e-taxis" height="230" />
</p>

| Pillar | Is | Changes here |
|---|---|---|
| [e-nous](https://github.com/damvolkov/e-nous) | the will — persona, skills, agents, commands, workflows, evals, specs; data only | doctrine |
| [e-arkhetypo](https://github.com/damvolkov/e-arkhetypo) | the body — project blueprints, stacks, CI sources; data only | templates |
| **e-taxis** | the hand — all the code: turns archetypes into running things, transpiles, evaluates and enhances the will, runs its workflows | tools |

**One system.** `make taxis` in e-nous or e-arkhetypo puts this CLI on the PATH, and `taxis` finds the brain from
any shell — no `--nous` to type. The first rung holding a valid e-nous checkout (`core/schema.yaml` and
`specs/base.yaml`) wins: `--nous PATH` (an invalid one fails, it never falls through) · `TAXIS_NOUS` · the nearest
ancestor of the cwd · `<git toplevel of the cwd, or the cwd>/../e-nous`, so e-arkhetypo and e-taxis find the
checkout beside them. None → exit `31`, naming every rung. `plan`, `verify` and `apply` stay profile-first: with
`--profile` nothing is located.

##### COMMANDS #####

Every command, one line each — `taxis <command> --help` gives its flags. `tests/unit/e_taxis/test_cli.py` fails when a command is missing here.

**Brain — transpile**

| Command | Does |
|---|---|
| `taxis transpile check` | Hold a checkout to its schema and every spec's law. |
| `taxis transpile run` | Project a core for one backend; --out for a pure export. |
| `taxis transpile reverse` | Read the live tree back: who moved each fragment since the last landing. |
| `taxis transpile trial` | Raise the real harness fenced on the render; check what it loaded. |

**World — catalog, install, undo**

| Command | Does |
|---|---|
| `taxis map` | The catalog, per target and profile. |
| `taxis plan` | What apply would do; writes nothing. |
| `taxis verify` | Run every wanted part's verify. |
| `taxis doctor` | Check the catalog's integrity. |
| `taxis apply` | Carry the plan out; dry unless --yes. |
| `taxis install` | Brain, then systems; dry unless --yes. |
| `taxis uninstall` | Take one part out; dry unless --yes. |
| `taxis history list` | Every recorded run. |
| `taxis history undo` | Revert the last recorded run. |

**Workflows**

| Command | Does |
|---|---|
| `taxis workflow run` | Run a workflow; exits 24 when a step failed. |
| `taxis workflow list` | Every workflow drawn: parameters, then D/S step chains. |
| `taxis workflow step` | Run one step inside a run a harness walks; one JSON line. |
| `taxis workflow put` | Keep a harness agent's answer as a semantic step's out. |
| `taxis workflow check` | Hold workflows to their static law; writes nothing. |

**soa-sweep steps**

| Command | Does |
|---|---|
| `taxis workflow soa-sweep frame` | Fix the frame from soa.yaml; an unknown topic fails here. |
| `taxis workflow soa-sweep ledger` | The seen ledger, for the frame's voices. |
| `taxis workflow soa-sweep fetch` | Every voice and entry page inside the window. |
| `taxis workflow soa-sweep ground` | Merge the findings; keep what a fetched page holds. |
| `taxis workflow soa-sweep fit` | Mark each finding have, considered or new. |
| `taxis workflow soa-sweep report` | Write report.md and report.json; record the ledger. |
| `taxis workflow soa-sweep deliver` | Post the summary and report.md to Discord. |
| `taxis workflow soa-sweep schemas` | Write (or --check) every soa-sweep port's JSON Schema. |

**reverse-distill steps**

| Command | Does |
|---|---|
| `taxis workflow reverse-distill guard` | Fix the scope; exit 3 when nothing is past the base. |
| `taxis workflow reverse-distill intake` | The range's commits and touched files. |
| `taxis workflow reverse-distill index` | e-nous, e-arkhetypo and the project into the code graph. |
| `taxis workflow reverse-distill scan` | The range's changed files and impacted symbols. |
| `taxis workflow reverse-distill drift` | The project's own drift checks, read. |
| `taxis workflow reverse-distill inventory` | Every plane, without a model: what the cores do not say. |
| `taxis workflow reverse-distill grade` | Merge the miners, propagate contradictions, weigh. |
| `taxis workflow reverse-distill report` | Join verdicts and reviews; write report.md and briefs. |
| `taxis workflow reverse-distill ship` | Run the commands that apply the musts. |
| `taxis workflow reverse-distill schemas` | Write (or --check) every port's JSON Schema. |

**soa-assess steps**

| Command | Does |
|---|---|
| `taxis workflow soa-assess intake` | Resolve a technology to its repository and package. |
| `taxis workflow soa-assess inventory` | What lives here in the candidate's domain, no model. |
| `taxis workflow soa-assess health` | Dated health KPIs from no-auth sources. |
| `taxis workflow soa-assess bench` | Install every arm fenced; run the plan interleaved. |
| `taxis workflow soa-assess stats` | The paired bootstrap interval against the threshold. |
| `taxis workflow soa-assess report` | Write report.md and assess.json; index the verdict. |
| `taxis workflow soa-assess schemas` | Write (or --check) every soa-assess port's JSON Schema. |

**Evaluation and enhancement**

| Command | Does |
|---|---|
| `taxis eval run` | Measure a target's subjects; exits 24 only when a node broke. |
| `taxis eval graph` | Print and prove the evaluator's graphs. |
| `taxis eval needs` | An evaluation's open needs; exits 1 while any is open. |
| `taxis enhance run` | Enhance on a reason, in a sandbox; verdicts and patches. |
| `taxis enhance graph` | Print and prove the enhancer's graphs. |
| `taxis enhance promote` | Apply an enhancement's patches to the checkout; a human command. |
| `taxis reports show` | A plane run's report, rebuilt from its ledger. |

**Schedules**

| Command | Does |
|---|---|
| `taxis schedule list` | Every schedule with its timer's state; orphans too. |
| `taxis schedule apply` | Render the schedules into systemd user timers; dry unless --yes. |
| `taxis schedule run` | Run one now through systemd; exits 33 unless it succeeds. |

**Tools**

| Command | Does |
|---|---|
| `taxis logo` | Deterministic family wordmarks into assets/. |
| `taxis repo resolve` | The commit a ref names on a remote. |
| `taxis repo tree` | Every file under a path at a ref. |
| `taxis repo extract` | Unpack a path at a ref into a directory. |

##### RUN #####

```bash
taxis install --target T [--nous PATH] [--profile P] [--ref REF | --worktree] [--yes]
              [--accept-licence ID] [--confirm ID] [--json]         # brain, then world: one run, one undo
taxis transpile check|run|reverse|trial …                           # the brain alone: docs/transpile.md
taxis workflow run ID [--nous PATH] [name=value ...]                # a corpus workflow, end to end: docs/workflow.md
taxis workflow list [--nous PATH] · check [ID ...] [--nous PATH]    # every workflow; its static law
taxis workflow reverse-distill guard|intake|index|scan|drift|inventory|grade|report|ship|schemas --rundir DIR [--nous PATH] …
taxis workflow soa-sweep frame|ledger|fetch|ground|fit|report|deliver|schemas --rundir DIR [--nous PATH] …
taxis workflow soa-assess intake|inventory|health|bench|stats|report|schemas --rundir DIR [--nous PATH] …
taxis eval run T [IDS] [--nous PATH] [--cadence C] [--only M,...] [--candidate RUN] # the evaluator, read-only
taxis enhance run T [IDS] [--nous PATH] (--from R | --directive D | --manual) # verdicts + patches, in a sandbox
taxis enhance promote [RUN] [--nous PATH] [--ids …] [--yes]         # a human command: the patches into the checkout
taxis eval graph|needs · enhance graph · reports show [RUN] [--nous PATH]
taxis schedule list|apply [--nous PATH] [--yes] [--json] · run ID   # core schedules ⇄ systemd user timers taxis-<id>
taxis map    [--target T] [--json]                                  # the catalog: targets, scope, rollout per profile
taxis plan   --target T [--profile P | --nous PATH] [--json]        # wanted ⨝ catalog, requires order, probed
taxis verify --target T [--profile P | --nous PATH] [--json]        # every wanted part's verify, all of them
taxis doctor [--json]                                               # schema, ids, requires DAG, primitives, owners
taxis apply  --target T [--profile P | --nous PATH] [--only id,...] [--dry-run] [--yes]
             [--accept-licence ID] [--confirm ID] [--json]          # carry the plan out; dry unless --yes
taxis uninstall ID --target T [--cascade] [--yes]                   # one part (and its dependents) out; dry unless --yes
taxis history list · undo                                           # every run that wrote; revert the last one
taxis logo NAMES [--out DIR] · repo resolve|tree|extract URL REF …  # wordmarks; deterministic git reads on a remote
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
uninstall failed `11` · transpile `17`–`22` (docs/transpile.md) · nothing to distill `3` · workflow `23`–`26`, planes `27`–`30`
(open needs and refused promotions `1`), lock held past the wait `75` (docs/workflow.md) · no e-nous checkout `31` · schedule refused `32`, a schedule
run that did not succeed `33` · soa-assess `34`.
The report always prints first.

`TAXIS_NOUS` is the e-nous checkout read when `--nous` is not given (One system, above).
`TAXIS_CATALOG` points at another catalog root; `TAXIS_TIMEOUT` bounds each probe (seconds, default 10).
`TAXIS_NPM_PREFIX` is where `npm -g` installs (default: npm's own prefix); `TAXIS_DOWNLOAD_TIMEOUT` bounds
a binary download (seconds, default 300); `TAXIS_TEMP` stages downloads (default: the system temp dir).
`TAXIS_SCHEDULE_UNITS` is where `taxis schedule apply` writes its `taxis-<id>.service|.timer` (default
`~/.config/systemd/user`); it only ever touches files of that name carrying its header.
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
                          # reverse-distill's deterministic steps, the evaluator and the enhancer (docs/workflow.md)
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
