# Decisions

Every architectural decision: date, the decision, the evidence, what was rejected and why.

## 2026-10-28 — Unattended runs are systemd user timers rendered from the core

**Decision.** `core/tekton/config/schedules.yaml` declares each schedule (calendar, taxis argv steps); `taxis schedule
apply` renders `taxis-<id>.service|.timer` into the user manager, calendars checked by `systemd-analyze calendar`.
**Evidence.** The machine already runs user timers (`openhuman-image`, `openhuman-mcp`, the old `ops-eval@*`); the
old eval timers had been failing nightly since `ops/` retired (`ModuleNotFoundError: No module named 'ops'`) because
their command lived in hand-installed units, not in the core. `Persistent=true` catches missed runs after a suspend.
The units' PATH comes from `~/.config/environment.d/` — the manager's plane — verified from a unit: claude, opencode,
node, taxis, uv, git, landrun all resolve.
**Rejected.** cron (no catch-up, no per-run journal, a second scheduler beside the one already used); APScheduler or
any in-process daemon (a long-lived process to keep alive for what the OS does); Claude Code cloud routines (remote:
they cannot see the live tree or the local GPU stack).

## 2026-10-28 — Workflows run end to end in either harness; Claude gets a native workflow

**Decision.** A core workflow is transpiled to `~/.claude/workflows/<id>.js` (Claude Code dynamic workflow) by a
deterministic `script` combinator, and to `~/.config/opencode/workflows/<id>.md` walked by `/workflow` in OpenCode.
`taxis workflow run <id> --harness claude|opencode` launches either headless; without `--harness` the taxis engine runs.
**Evidence.** Probed 2026-10-28: `claude -p '/<id> {args}' --allowedTools 'Workflow(<id>)'` ran a saved workflow
headless, args passed, `agent(…, {schema})` validated (cost $0.42, mostly session overhead). OpenCode 2.2.0 has no
native workflow and no `run --command`; `opencode run --standalone "/workflow <id> …" </dev/null` expands the command —
the earlier hang was an open stdin. The Workflow script has no shell or filesystem: `run` nodes become an agent that
calls `taxis workflow step`, agent answers are persisted with `taxis workflow put`.
**Rejected.** An LLM writing the JS per workflow (non-deterministic, unreviewable drift); the taxis engine as the only
path (the harness then never runs its own native form, and the user cannot launch it from inside a session).

## 2026-10-28 — `taxis workflow list` draws each graph with a renderer of our own

**Decision.** Chains of single-parent nodes print on one line with `→`, every other node names its parents with `←`;
`D`/`S` mark deterministic and semantic nodes, `↻n` a loop, `?k=v` a condition. Exact by construction.
**Evidence.** Measured on the four corpus workflows: graphtty 0.1.8 (MIT, 232k downloads/month) routes long edges
through boxes (`tria│e`, `publ│sh`) and takes ~50 lines for `converge`; phart 2.1.0 (networkx) draws false edges
(`history → triage`, drops `history → report`). A graph with a false edge is worse than none.
**Rejected.** graphtty and phart for the reasons above; mermaid-ascii 1.6.1 (Go, MIT, 1614 stars) is untested — its
binary download was not authorized in the session; to revisit as a catalog binary if boxes are wanted.

## 2026-10-28 — Deterministic node commands live under `taxis workflow <id>`, hidden

**Decision.** A workflow's deterministic steps are `taxis workflow <workflow> <node>` (reverse-distill, soa-sweep,
soa-assess), hidden from `--help`: only the graph calls them. `taxis distill` leaves the top level.
**Evidence.** Damien, 2026-10-28: distill is a workflow, not a base command; the top-level help must show what a
human types, not the plumbing.
**Rejected.** One top-level group per workflow (the help grows with every workflow); a single generic `step` command
for all logic (the node's behaviour must be a typed command of its own to be tested).
