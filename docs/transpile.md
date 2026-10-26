# e-taxis — transpile

An e-nous core into each harness, from its specs — and back, to see what moved. Deterministic, versioned,
undoable. e-nous holds the data (`core/`, `core/schema.yaml`, `specs/`); this is the only code that reads it.

## 1. No hand-written models

The checkout declares its own shapes: `core/schema.yaml` (what the core may hold) and `specs/base.yaml` (`types`,
`kinds`: what a spec may say). `transpile/engine/schema.py` parses their type grammar and compiles it on the fly
to closed msgspec types; the same AST yields the leaf paths the coverage law walks. A new entity, module, field or
spec kind is a YAML change in e-nous, never a model here.

```
expr := term ('|' term)*
term := list<expr> | map<expr, expr> | enum[a, b] | {k: expr, …} | 'literal' | word
```

## 2. Pipeline

```
GitNous (core + specs at one ref) ─▶ CoreModel · SpecModel (compiled) ─▶ check (schema + law) ─▶ render ─▶ plan / apply / reverse
```

| Module | Layer | Holds |
|---|---|---|
| `transpile/models` | models | `NousTree` (one raw read), `Report` (findings + stamp), errors, `NousPort` |
| `transpile/engine` | processors | `Schema` (grammar → types, leaves), `CoreModel`, `SpecModel`, `SpecLaw` — pure |
| `transpile/adapters` | adapters | `GitNous`: `git archive` of `core/` + `specs/`, or the worktree; `{source}` envelopes resolved, confined |
| `transpile/services` | services | `CheckService` |
| `transpile/commands` | cli | `taxis transpile …` |

## 3. Commands

```
taxis transpile check   --nous PATH [--ref REF | --worktree] [--json]          # schema + every spec's law
taxis transpile run     --target T|all --nous PATH [--ref …] [--out DIR] [--yes] [--json]   # T1–T3
taxis transpile reverse --target T|all --nous PATH [--ref …] [--json]                       # T4
```

`check` exits 20 on any blocking finding. Kinds are `specs/base.yaml · report.kinds`; `signal` (upstream moved
past the verified version) informs, every other kind blocks. The stamp carries the checkout, the commit read and
every spec's model version.

## 4. Phases

| Phase | Delivers | Proof |
|---|---|---|
| T0 | compiled models, `GitNous`, `transpile check` | seeded mutations caught as their kind; e-nous clean |
| T1 | row engine, combinators, formats, `run --out` (claudecode, opencode) | bytes equal to `backup/e-nous/golden` modulo the listed v2 changes |
| S1 | Landlock fence, sandbox, ghost harnesses | e2e: `run --yes` in the sandbox, the ghost sees persona, skills, agents |
| T2–T3 | total ownership, fragment plan, report, apply through the journal | e2e: idempotent, exact undo, no leak |
| T4 | reverse: three-way per fragment | e2e: seeded harness edits found on their row |
| T5 | hermes, openhuman: bindings, links, foreign tables and items | golden + nomos ghosts |
| T6 | `taxis brain` and its adapter retired; `install` on transpile | install suite green |
| E1–E3 | evaluators: law + MCP → security → routing and effect | e2e in the sandbox |
