# e-taxis — workflow

Corpus workflows, run: graphs of steps — a command, or a headless agent session — declared as data in an e-nous
checkout (`core/tekton/workflows/<id>/`) and executed here. e-nous holds the definitions; e-taxis holds the engine,
the CLI and reverse-distill's deterministic steps. Ported from e-nous's legacy `ops/` (branch
`feat/restore-ops-workflows`, tag `archive/ops-v1`) nearly as it was; the v1 transpiler is not ported — the
transpiler is `docs/transpile.md`.

## 1. Pipeline

```
GitNous (the checkout as it stands) ─▶ WorkflowReader (typed Workflow, static law, loop unrolled) ─▶ bind params
  ─▶ pin HEAD · run folder ─▶ FlockLock (waited for) ─▶ DagExecutor (one TaskGroup, one Semaphore) ─▶ WorkflowStep
  ─▶ ledger.jsonl ─▶ report.md · exit 0, or 24 when a step failed
```

| Module | Layer | Holds |
|---|---|---|
| `workflow/models` | models | `Workflow` (+ `problems()`, `writers()`), `GraphSpec`/`StepSpec`, `NodeRun`/`RunManifest`/`RunReport`, metrics, the distill chain (`models/distill.py`), errors, ports |
| `workflow/engine` | processors | `WorkflowReader` (tree → graph), `ParamBind` (parameters as quoted variable references), `DagExecutor` — no I/O of their own |
| `workflow/adapters` | adapters | `ShellCommand` (argv, stdout to a file, live stderr, timeout), `JsonlLedger`, `FlockLock`, `OpencodeAgent` (headless, fenced when read-only) |
| `workflow/services` | services | `WorkflowStep` (the one node kind), `WorkflowRun` (end to end) |
| `workflow/distill` | services | reverse-distill: `DistillScope`, `DistillGraph`, `DistillDrift`, `DistillInventory`, `VersionMatrix`, `DistillGrade`, `DistillReport`, `DistillStore` |
| `workflow/commands` | cli | `taxis workflow …`, `taxis distill …` |

The workflow is read through the transpiler's own `GitNous` (worktree), so `{source: nodes/<id>.yaml}` envelopes
resolve in one place. Where things live is what `core/schema.yaml` says: the workflow folder is its entity path,
port schemas are `<folder>/schemas/<Model>.json`, hooks the files of the config asset folder `hooks`.

One node kind exists, so the executor takes the node whole; a second kind becomes a frozen table use → node. The
legacy `importlib` loader is gone. graphlib (stdlib, already this repo's DAG tool) replaces rustworkx.

## 2. Commands

```
taxis workflow run ID --nous PATH [name=value ...]     # run; live rows on stderr, report on stdout; 24 if a step failed
taxis workflow list --nous PATH                        # every workflow: parameters, steps, when, after
taxis workflow check [ID ...] --nous PATH              # static law of every (or the named) workflow; 23 if one fails

taxis distill guard     --rundir DIR --project P [--branches "a b"] [--since REF] [--work TEXT]   # 3: nothing to do
taxis distill intake    --rundir DIR
taxis distill index     --nous PATH --rundir DIR
taxis distill scan      --rundir DIR
taxis distill drift     --rundir DIR
taxis distill inventory --nous PATH --rundir DIR
taxis distill grade     --nous PATH --rundir DIR
taxis distill report    --nous PATH --rundir DIR
taxis distill ship      --nous PATH --rundir DIR
taxis distill schemas   --nous PATH [--check]
```

`--nous` is taken only where the step reads e-nous. Exit codes: `3` nothing to distill · `23` a workflow that
cannot be read or bound · `24` a run with a failed or broken step · `25` a distill artifact missing or misfit ·
`26` a command that failed · `75` the lock held past the wait.

Settings (`TaxisSettings`, environment): `TAXIS_WORKFLOW_REPORTS` (`.reports`, relative to the checkout),
`_CONCURRENCY` (4), `_TIMEOUT` (1800 s per step), `_LOCK_WAIT` (600 s), `_OPENCODE` (`~/.config/opencode`, the live
tree agents are driven from), `_MODEL`, `_WRITABLE` (what a read-only session may write); `TAXIS_DISTILL_BLUEPRINT`
(`~/workspaces/damien/e-arkhetypo`), `_REF` (`origin/main`), `_GRAPH` (`codebase-memory-mcp`), `_CACHE`, `_SCOPE`
(`core`, `specs/tekton`), `_CANDIDATES` (12), `_WORKFLOW` (`reverse-distill`); `TAXIS_LOCK` (the token a parent run
hands its steps).

## 3. A run

```
<nous>/.reports/workflows/<id>/<UTC>-workflow-<id>-<sha7>/
  run.json          RunManifest: workflow, bound parameters, e-nous path and HEAD, the graph
  ledger.jsonl      one NodeRun per line, fsynced — the truth; a rerun of the same folder pays only for what moved
  nodes/<step>/out.md   what each step said; an agent step's JSON answer is read back from here
  distill/*.json    reverse-distill's typed artifacts · briefs/ · report.md
```

Every step sees `{{run}}`, `{{rundir}}`, `{{nous}}` and, in a loop, `{{iteration}}`, besides the declared
parameters. A `run:` step is `bash -lc` in the checkout; exit 3 is "nothing to do" (`skip`, and every step after it
skips — zero tokens). An agent step drives the live tree's agent (the lead, `orchestrator`, when no `actor`), told
the run's id, folder and every ancestor's output. `when:` idles a step; a `loop:` is unrolled into `max` copies and
every copy after an ending `until` check (closed, or the same open set twice) idles.

## 4. Read-only agent steps

OpenCode 2.0.28, measured on this machine (2026-10-26):

- `OPENCODE_CONFIG_CONTENT` is read only by a server started from the run's own environment: `opencode run
  --standalone` (and `opencode api --standalone`). `opencode debug config|agents` ask the background service
  (`opencode serve --service`), which never sees the variable — they cannot show an injection.
- On a standalone server the injection is honoured and normalized: `{"agent": {X: {"permission": {"edit": "deny",
  "write": "deny"}}}}` arrives as `agents.X.permissions: [{action: edit, resource: "*", effect: deny}, …]`
  (`opencode api --standalone GET /api/config`). v2 has no `write` action; `edit` is the file tools.
- The agents keep `shell: allow` (`scout-codegraph`: `{action: shell, resource: "*", effect: allow}`). `edit: deny`
  does not stop `sed -i`, `>` or `git apply`: that is how a read-only session wrote into e-nous. Denying `shell`
  would blind the miners (git, the code-graph CLI).

So read-only is enforced structurally: the session runs under Landlock (`landrun`, the trial's own fence):
read and execute everywhere, write only OpenCode's cache/data/state (`TAXIS_WORKFLOW_WRITABLE`) and a private
`TMPDIR`, any network, the environment passed by name (no value lands in an argv). `--best-effort` could silently
weaken, so the fence's canary runs before every read-only session; a fence that does not hold refuses the step. A
standalone OpenCode server boots under the fence (`opencode api --standalone GET /api/location`), and a write into
the checkout is refused (`Permission denied`). The `edit: deny` injection stays as defence in depth.

## 5. Defects fixed

Each one has a test that was run against the legacy behaviour first and failed, then passed with the fix.

| # | Defect | Fix |
|---|---|---|
| 1 | grade read `nodes/mine-arkhetypo`; the node is `mine-blueprint` | the answering steps are read from the workflow's output ports (`Workflow.writers("Mining" \| "Judgements" \| "Reviews")`): one source of truth, no id in code |
| 2 | scan listed the working tree's changes (and the graph's paged, worktree-polluted list) | changed files are `git diff --name-only base...head` over the scope's branches; only the impacted symbols come from the graph. e-gnosis since 7ef77f6: 468 files, none under `.claude/` (the graph's `detect_changes` counted ~475, agent worktrees included) |
| 3 | a contradiction reached only the places its miner named (awa → PgQueuer missed `test-py-tdd/references/lib.md:12`) | `Candidate.replaces` names the replaced term(s) (required for `contradicts`); grade greps each (`git grep -w -i -F`, tracked and untracked) across `core/` and `specs/tekton/`, adds every hit as evidence and, where the path is a known part of an entity, a spec, the stack or a config module, as a target; a term the core never states stops the candidate. `Grade.propagated` lists what was added |
| 4 | `{{param}}` spliced into `bash -lc`; the report's `apply:` commands likewise | parameters travel as `TAXIS_PARAM_<name>` variables, the placeholder becomes a reference quoted for its context (bare, double, single quotes); `apply:` commands `shlex.quote` every value and read the proposal's text from its brief file. Tested with `"`, `'`, `$(…)`, backticks, `;` and newlines in a real bash |
| 5 | `workflow run` exited 0 when a step failed | after the report, `RunFailedError` (exit 24) when any step is `fail` or `error` |
| 6 | read-only not enforced on OpenCode 2 | §4: a Landlock fence around the session, canary-checked; config injection kept |
| 7 | (emaintenance, W2) `evaluate` runs after a skipped `promote` and evaluates the old entity | recorded, not fixed: `promote` is `when: publish=true`; an idle step is green, so `evaluate` runs on the unpromoted tree. W2 should make `evaluate` read the sandbox candidate when `promote` idled, or idle with it |
| 8 | the run lock refused a second run outright | the lock is waited for (`TAXIS_WORKFLOW_LOCK_WAIT`, polling), the holder named once on stderr; only a lock held past the wait fails (75) |

Found on the way and fixed, each with its test:

- **intake dropped every commit with an empty body.** `str.strip()` counts `\x1e`/`\x1f` as whitespace, so the
  record lost its last field. e-gnosis since 7ef77f6: 148 of 152 commits were kept; now all.
- **a stopped candidate could become a proposal** when a judge judged it anyway; stopped candidates now only reach
  `rejected`.
- **a candidate id was a path**: it names its brief file and branch; ids are now one safe word (stopped otherwise).
- `codebase-memory-mcp` 0.12 deprecated raw JSON arguments and renamed `impacted_symbols` → `impacted`: calls go
  through `--args-file`, both names are read.

## 6. Decisions (2026-10-26)

- **graphlib over rustworkx** — evidence: the executor orders a dozen steps; graphlib is the repo's DAG tool
  (`ResolverService`). Rejected: adding rustworkx for no measurable gain.
- **Read-only by Landlock, not by config** — evidence §4. Rejected: denying `shell` (blinds the miners); running in
  a throwaway copy (absolute paths still reach the repo); detect-and-revert (concurrent writers make the blame
  ambiguous, and the write already happened).
- **Changed files from git, impacted symbols from the graph** — evidence §5.2. Rejected: paging the graph's list
  (still the working tree).
- **`replaces` declared by the miner, validated by grep** — the term is the miner's claim, the grep its proof.
  Rejected: deriving terms from the sketch (a model's prose is no deterministic input).
- **One node kind injected whole** — rejected: a registry for one entry.

## 7. W2

`enhance` and `eval` — what `emaintenance` and `converge` need (`op enhance run|promote`, `op eval run|graph|needs`),
with the v2 render in place of the v1 transpiler wherever the legacy code rendered a sandbox. `DistillReport`
already writes `taxis enhance run …` for a place of the core that is no entity; `ship` runs only the emaintenance
musts. Defect 7 lands with it.

## 8. e-nous side

e-taxis does not edit e-nous. The edits e-nous must take:

1. **reverse-distill `run:` lines** — `uv run op distill <step> --rundir {{rundir}}` → `taxis distill <step> --rundir
   {{rundir}}`, plus `--nous {{nous}}` on `index`, `inventory`, `grade`, `report`, `ship`. `guard` keeps its
   parameters and drops the quotes the binder now owns: `taxis distill guard --rundir {{rundir}} --project
   {{project}} --branches {{branches}} --since {{since}} --work {{work}}` (quoted or not, a value arrives intact).
   `taxis` must be on the PATH of the login shell a step runs in (e.g. `uv tool install` from the e-taxis checkout).
2. **Schemas** — `taxis distill schemas --nous <e-nous>` regenerates `core/tekton/workflows/reverse-distill/schemas/`:
   `Candidate` gained `replaces`, `Grade` gained `propagated` (`--check` fails until then).
3. **Miner instructions** — `mine-harness` and `mine-blueprint` must fill `replaces` for every candidate whose
   relation is `contradicts` (the term the core states today), and keep candidate ids to letters, digits, `.`, `_`,
   `-`.
4. **Agents driven headless must be drivable** — the live tree marks `researcher`, `scout-codegraph`,
   `auditor-verdict` and `verifier-adversary` `mode: subagent`; `opencode run --agent` on a subagent falls back to
   the default agent, so the driver refuses them and reverse-distill's five agent steps fail until those agents are
   `mode: all` (or the workflow names drivable ones).
5. **emaintenance / converge `run:` lines** — `uv run op …` stays until W2 ports `enhance` and `eval`; then the same
   rewrite to `taxis … --nous {{nous}}`.
6. **Eval ledgers** — `ops/evaluator/ledgers/` is brain data, not tooling: move it to `core/tekton/evals/<entity>/`
   (queries and tasks per subject) before W2 reads it from `--nous`.
7. **Retire `ops/`** — once W1 and W2 run from e-taxis, `feat/restore-ops-workflows` is discarded and e-nous keeps
   no `ops/`.
