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

## 2026-10-29 — soa-compare ranks on one fixed rubric, over the terms measured for every subject

**Decision.** `CompareRank` weighs rust 0.25, recency 0.15, cadence 0.10, dependents 0.15, downloads 0.15, scorecard
0.10, licence 0.10; a rival earns a bench only when it beats its incumbent by 0.05; stars break ties and never score.
A contest totals only the terms measured for all its subjects. `rust` is true when Rust, C or C++ hold ≥ 20 % of the
repository's bytes by GitHub `/languages`.
**Evidence.** 2026-10-29 run: GitHub's anonymous limit (60/h) left one subject without dependents and stars, and the
old total read the gap as 0 — a rate limit decided the verdict. On common terms msgspec kept against orjson (0.8146
vs 0.8497 is inside the margin) and wreq against pyreqwest, both on 6 of 7 terms. Bindings are mostly Python bytes:
msgspec 40 % C, orjson 44 % Rust; a pure package holds 0 %, so the old > 50 % cut called both pure.
**Rejected.** An LLM ranking the rivals (non-deterministic, unauditable); imputing a missing KPI (a guess presented as
a measure); stars as a term (popularity, not maintenance — the house order says maintained over popular).

## 2026-10-29 — `query` fills missing kwargs through a small local model, scout tier as fallback

**Decision.** Every workflow takes `query`; when kwargs are missing, `WorkflowKwargs` asks the local vLLM
(OpenAI-compatible, strict `json_schema` structured output) for them, then the scout tier if the local endpoint fails,
and binds the answer through the same typed checks as explicit kwargs. Recorded in the ledger as node `kwargs`.
**Evidence.** The schema comes from the workflow's own params, so the output is validated, never trusted; explicit
kwargs always win; the default tier is the local Gemma 4 26B-A4B, so a query-only run costs no cloud call.
**Rejected.** Regex parsing of the query (brittle beyond `k=v`); the harness's main model (cost and latency for a
deterministic-shaped extraction); no fallback (a stopped GPU stack would break every query-only run).

## 2026-10-29 — `claude -p` runs without the background wait ceiling

**Decision.** The Claude harness launches with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`; taxis's own harness limit
bounds the run.
**Evidence.** soa-compare through Claude stopped after exactly 10 idle minutes with its workflow still running and its
result dropped; with the ceiling off the same run finished `ok 4 · skip 7`.
**Rejected.** Shorter workflows to fit the ceiling (the bench legitimately runs longer); polling from taxis (a second
wait loop beside the one claude already has).

## 2026-10-29 — The research workflows are `radar-field`, `radar-tech`, `radar-stack`

**Decision.** soa-sweep, soa-assess and soa-compare become radar-field, radar-tech and radar-stack; one `/radar
<field|tech|stack>` command replaces /soa, /assess and /compare. The config is `radar.yaml`, the family `radar`, run
artifacts live under `radar/`, the state under `TAXIS_RADAR_STATE`. The Python modules keep their verbs
(`sweep`, `assess`, `compare`): they name what the code does, not the product.
**Evidence.** Damien could not tell the three apart by name, and the family is widening past agents (GEO). The root
traces to the Technology Radar, whose rings (adopt, trial, assess, hold) are this family's verdicts; the second
word reads the scope broad to narrow.
**Rejected.** horizon- (horizon scanning fits the field survey only, not the two that look at what we run); recon-
(memorable, no vocabulary behind it); a three-word id (the scope fits one word).
