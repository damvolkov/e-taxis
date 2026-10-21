# e-taxis — design

τάξις, *arrangement, order of battle*: e-taxis mounts an agent harness in two halves. First the brain: an
e-engineer core (persona, skills, agents, commands, config, MCP) projected into the harness's tree. Then the world
that brain expects — the CLIs, MCP servers, plugins, hooks, environment, managed files and services — in order,
verified, and undoable.

It runs two ways from one core: as the installer plane of e-engineer (`op` drives it after `op transpiler apply`) and
standalone, for anyone with Claude Code (`uvx e-taxis …`), from its own catalog and profiles.

## 1. Boundary

e-engineer owns the **content**: `core/base`, `core/<facet>`. e-taxis owns everything **operational**: the content
contract (`models/core.py` — every entity, its slots, where it lives), each harness's projection of it, the
catalog, and the install. The e-engineer transpiler migrates here harness by harness; a projection lands only when
it renders byte for byte what the transpiler wrote (Claude Code: 202 files identical, settings and MCP equal,
2026-10-15).

| | brain (`taxis brain`) | world (`taxis apply`) |
|---|---|---|
| writes | what the harness **reads** | what the brain **needs to exist** |
| order | first | second; `taxis install` runs both as one undoable run |
| config keys | the keys its projection owns | only the keys **its** recipes declare (`owns`); never one the brain owns |

Every key of every harness config file has exactly one owner. A recipe that merges into `settings.json` lists the keys
it owns; a key the transpiler also claims is a catalog error, caught by `taxis doctor`.

## 2. Two inputs, one join

- **What is wanted** — a *source*: e-engineer's stack registry (`core/common/stack.yaml`, `core/<facet>/stack.yaml`:
  part id, kind, pin, the backends it serves) or, standalone, a *profile* shipped with e-taxis (`house`, `company`,
  `minimal`).
- **How it is installed** — the *catalog*, shipped with e-taxis: one entry per part id.

The resolver joins them: a wanted part with no catalog entry is reported (`unknown`), never guessed.

## 3. The catalog entry

```yaml
id: otel                         # the part id the source uses
kind: service                    # harness · mcp · plugin · hook · cli · service · env · file · managed
targets: [claudecode, opencode]  # where it applies; `system` = harness-independent
scope: service                   # machine · user · project · service · org
requires: [phoenix]              # parts that must come first (a DAG)
recipes:                         # one per target, or `any`
  any:
    primitive: compose           # uv-tool · npm · binary · compose · claude-plugin · claude-mcp · settings · file · env
    with: {template: stack/watch/otel, path: ~/.config/compose/otel}
probe: docker inspect -f '{{.State.Running}}' otel        # is it there, which version
verify: docker logs otel 2>&1 | grep -q 'Everything is ready'
uninstall: {primitive: compose, with: {path: ~/.config/compose/otel, down: true}}
footprint: [~/.config/compose/otel, ~/.config/compose/data/otel]
owns: []                         # config keys this entry writes (settings/env primitives)
gate: {licence: null, secrets: [], confirm: false}
flags: {}                        # what the bench forced (e.g. Beads: --skip-agents --skip-hooks)
status: {profile: {house: floor, company: floor}, checked: 2026-10-15, evidence: e-engineer docs/bench/observability.md}
```

`status.checked` and `evidence` are what the automated stack review reads: a scheduled, deterministic workflow re-probes
versions, licences and health, compares them with the catalog and opens a PR with its report.

## 4. Run

```
taxis plan   --target claudecode --profile house      # read-only: wanted ⨝ catalog, DAG order, probe, diff
taxis verify --target claudecode --profile house      # read-only: every entry's verify, fail-fast report
taxis doctor                                          # read-only: catalog integrity — schema, DAG, ownership clashes
taxis map                                             # the catalog: compatibility, versions, status per profile
taxis apply  --target claudecode --profile house      # writes: needs --yes; journal entry per step
taxis uninstall <id> · taxis history list · undo      # the journal reverts what apply wrote
```

`apply` is idempotent: a step whose probe already matches is skipped. Every write goes through the undo journal the CLI
template ships, so `taxis history undo` reverts a run.

## 5. Shape

Hexagonal, as the template is. Ports: `SourcePort` (wanted parts), `CatalogPort` (entries), `PrimitivePort` (probe ·
install · uninstall per primitive), `ProbePort` (run a shell probe). Adapters: one per source, one per primitive.
Services: `ResolverService` (join + DAG through `graphlib`), `PlanService` (probe + diff), `VerifyService`. A new
harness is new adapters and catalog rows; the core does not change.

## 6. The brain

| core entity | where it lives in the core | Claude Code |
|---|---|---|
| persona | `core/base/persona.yaml` + `core/engineer/persona.yaml` (a slot lives in one layer) | `CLAUDE.md`, fixed blocks |
| skill | `core/engineer/skills/<id>/skill.yaml` + body + `references/` | `skills/<id>/SKILL.md` + references |
| agent | `core/engineer/agents/<id>/agent.yaml` + prompt | `agents/<id>.md`; denied tools → `disallowedTools` |
| command | `core/engineer/commands/<id>/command.yaml` + template | `commands/<id>.md`; named arguments |
| main · permissions · hooks | `core/engineer/config/*.yaml` | `settings.json` owned keys; `rules/instructions.md`; `hooks/*` |
| mcp | `core/engineer/config/mcp.yaml` + `mcp/*` | user-scope registrations; `mcp/*` |

The plan is three-way — render, live tree, the digests of the last install (`brain:<target>` in the store) — so an
edit by hand is an `overwrite`, shown before it happens. Nothing is deleted: a governed folder's leftovers are
`orphan`s. Every file, key and registration is a journal effect: undo restores bytes, prior key values, prior
registrations, and the directories a run created.

## 7. Phases

| Phase | Delivers | Writes |
|---|---|---|
| P1 | models, catalog loader, sources (e-engineer stack, profiles), resolver, `map` · `plan` · `verify` · `doctor` | nothing |
| P2 | primitives `uv-tool`, `npm`, `binary`, `settings`, `env`, `claude-mcp`, `claude-plugin`; `apply` · `uninstall` with the journal | user, machine |
| P3 | `compose` (from arkhetypo' stack fichas) and the project scope | service, project |
| P4 | the transpiler's export target → a versioned artifact per harness (Claude plugin, OpenCode config dir) | — |
| P5 | OpenCode and OpenHuman adapters | — |
| P6 | the stack review workflow: scheduled, deterministic, reports + PR | — |

Status (2026-10-15): P1, P2 and the Claude Code brain shipped. P2 writes the user and machine scopes; `env` is the `settings`
primitive's env merge under its own name; `compose` answers `NotSupportedYet` and the plan reports it, and
every project-scope entry, as `deferred`. World effects (files placed, JSON keys with prior values, marked
blocks, CLI registrations with their inverse) live in the journal entry, so `taxis history undo` reverts an
apply or an uninstall — a failed one included.
