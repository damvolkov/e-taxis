# workflows — the graph entity

A workflow is `core/tekton/workflows/<id>/`:

- `workflow.yaml` — `id, description, parameters, nodes, loop, output, triggers`;
- `nodes/<node>.yaml` — one file per node, named after its id, listed in
  order as `{source: nodes/<node>.yaml}`: `id, depends, when`, then what runs
  it (`run` a command · `actor` + `instruction` an agent · `instruction`
  alone the lead), `hooks`, typed `inputs`/`outputs` ports, `steps`,
  `timeout`, `readonly`;
- `graph.svg` and `README.md` — the human view, generated (`make graphs`),
  never written by hand.

e-serde embeds the node files and `msgspec` decodes the whole into the typed
`Workflow` (`ops/models/workflow.py`); every reader works on that model.
Reading checks it statically — unknown step, agent, hook or port, a port of
the wrong model, a cycle — so a miswired graph fails before a token is
spent. What an agent loads (skills, MCP, tools) belongs to the agent, not
to the node.

It is rendered by `specs/tekton/opencode/workflow.yaml` (`status: ready`,
house convention) into `workflows/<id>.md`: frontmatter + mermaid derived
from `depends` + steps + output.

The transpiler renders, never executes. OpenCode has no native workflow
type, so the flat file is an **interpreted specification** — a lead agent
(the `/workflow` command) walks the DAG and delegates each node.

Claude's native projection (`claude-script` JS) is a separate spec, still
pending.

## Create

1. A workflow is a **recurring multi-agent sequence with dependencies**.
   If one command template suffices, it is a command; if only judgment is
   needed, a skill. The graph earns its keep when order and parallelism
   matter.
2. `id` kebab-case == folder name. `parameters` are the invocation
   contract — commands pass names, renaming them is a `contract` move
   (versioning matrix); a missing parameter makes the interpreter stop,
   not guess.
3. A node is `id`, `depends`, `actor`, `instruction`. `actor: null` runs
   inline in the lead — use it for deterministic validation and
   reporting, not for judgment. Parallelism is structural: siblings with
   the same parents and no edge between them; a join node lists all
   parents in `depends`.
4. Every instruction ends with what the node **returns** ("Return
   {green, violations}…") — a node without a structured result is a
   defect and the run stops on it. Skip preconditions are declarative:
   "Only if X … otherwise return {skipped: true}".
5. **The graph has no cycles — and must not fake them.** Bounded rework
   lives in a `loop:` block, which the reader unrolls into finite copies
   before walking (below) — the cycle never enters the drawn graph, so the
   rule holds by construction, not by pretending. A one-shot recheck is two
   explicit nodes (`rework` conditioned on the violation, `regate` to
   re-verify once); a persistent failure ends the run and names the human
   command that continues it. A loop you cannot draw is a loop you cannot
   reason about.
6. Never create an instance of a kind whose spec is not `ready` (today:
   `tool`); never let craft outrun the spec — the spec agent keeps them
   honest (→ `flow-gen-research`).

## Update / retire

Source-only edit; the flat body is derived, so moving `nodes` moves
mermaid and steps in one render (`op transpiler check` proves it). The
matrix grades `nodes` as guidance and `parameters` as contract — trust
the ledger.

Before retiring: grep the id in `core/tekton/commands/` (the delegation
line), then delete and apply `--capability reset`, which prunes
`workflows/<id>.md`.

## The inhabited graph

A step is `run:` (a command: deterministic) or `actor:` + `instruction`
(an agent: semantic), optionally `when:` a parameter matches; siblings
run in parallel.

Two executors read the same source: `op workflow run <id> k=v…` (the ops
executor) and `/workflow <id>` (the coder's lead).

The `loop:` block is the sanctioned rework: `nodes` (the band to repeat),
`max` (a bound on copies), `until` (the check that ends it). Whoever reads
the graph unrolls it into `<id>_<k>` copies first, so what runs is a finite
chain, not a back-edge — rule 5 holds because a bounded repetition is
drawable and a drawable loop is a reasonable one. The `until` step decides
at every copy: exit 0 closes the loop; exit 1 leaves it open and the next
copy runs; printing what the previous check printed stalls it — two equal
verdicts mean no copy can change the outcome, and the run ends there, in
the human's hands. Every copy after an ending check is idle. `converge` is
the worked example.

`emaintenance` (one entity through evaluate → enhance/craft → review →
promote → ship) and `smaintenance` (specs drift) are the inhabited ones
(→ `scheduling.md`).

A workflow with no `intake` validation and no `report` is not a workflow,
it is a wish.
