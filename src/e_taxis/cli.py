"""e-taxis entrypoint: `taxis` — the command tree is two tables, and nothing under commands/ loads until it runs.

`GROUPS` and `CARDS` are the whole surface. `build` is the composition root: it turns the tables into
cyclopts apps and mounts every card by its `module:function` string, so importing this module imports no
command, and `taxis --help` or any group listing is served from the cards alone. The meta app runs the
`Launcher` first on every call: global options, the run's lifespan, injection by type, the error boundary.

Adding a command is one row in `CARDS` plus one plain function; a command that needs a new group adds a
row in `GROUPS`, parents before children. `tests/unit/e_taxis/test_cli.py` resolves every target, so a
typo fails the gate, never a user.

    taxis map      [--target T] [--json]
    taxis plan     --target T [--profile P | --nous PATH] [--json]
    taxis verify   --target T [--profile P | --nous PATH] [--json]
    taxis doctor   [--json]
    taxis install  --target T [--nous PATH] [--profile P] [--ref REF | --worktree] [--yes]
                   [--accept-licence ID] [--confirm ID] [--json]
    taxis apply    --target T [--profile P | --nous PATH] [--only id,...] [--dry-run] [--yes]
                   [--accept-licence ID] [--confirm ID] [--json]
    taxis uninstall ID --target T [--cascade] [--yes]
    taxis history  list · undo
    taxis transpile check [--nous PATH] [--ref REF | --worktree] [--json]   # schema + spec law; writes nothing
    taxis transpile run   --target T [--nous PATH] --out DIR [--ref REF | --worktree] [--json]   # pure export
    taxis workflow run ID [--nous PATH] [name=value ...]                  # a corpus workflow, end to end
    taxis workflow list [--nous PATH] · check [ID ...] [--nous PATH]
    taxis workflow step NODE --workflow W --rundir DIR [--nous PATH] [name=value ...] · put NODE --workflow W --rundir DIR --file F
    taxis workflow reverse-distill guard|intake|index|scan|drift|inventory|grade|report|ship|schemas [--nous PATH] --rundir DIR …
    taxis workflow soa-sweep frame|ledger|fetch|ground|fit|report|deliver|schemas [--nous PATH] --rundir DIR …
    taxis workflow soa-assess intake|inventory|health|bench|stats|report|schemas [--nous PATH] --rundir DIR …
    taxis workflow soa-compare intake|health|rank|bench|stats|report|schemas [--nous PATH] --rundir DIR …
    taxis eval run TARGET [IDS ...] [--nous PATH] [--cadence C] [--candidate RUN]   # the evaluator, read-only
    taxis eval graph [TARGET] · eval needs TARGET [--nous PATH] [--run R] [--owner O]
    taxis enhance run TARGET [IDS ...] [--nous PATH] (--from R | --directive D | --manual) [--cadence C]
    taxis enhance graph [TARGET] · enhance promote [RUN] [--nous PATH] [--ids ...] [--all-verdicts] [--yes]
    taxis reports show [RUN] [--nous PATH] [--json]
    taxis schedule list [--nous PATH] [--json]                            # every schedule and its timer's state
    taxis schedule apply [--nous PATH] [--yes] [--json]                   # core → systemd user timers; dry unless --yes
    taxis schedule run ID [--nous PATH]                                   # one now, through systemd; its result
    taxis logo NAMES [--out DIR] [--prefix P] [--background HEX] [--foreground HEX] [--force]
    taxis repo resolve URL REF                     # the commit a branch, tag or sha names
    taxis repo tree    URL REF [PATH]              # every file the remote holds at REF
    taxis repo extract URL REF PATH --dest DIR     # unpack it; `make infra` uses exactly this
"""

import sys
from importlib.metadata import version

from cyclopts import App

from e_taxis.harness.models.command import CommandCard, CommandGroup
from e_taxis.harness.runtime.launcher import Launcher

##### TREE #####
GROUPS: tuple[CommandGroup, ...] = (
    CommandGroup(path="history", help="Every run that wrote to the store, and the undo of the last one."),
    CommandGroup(path="repo", help="Deterministic git reads on a remote: resolve, browse, unpack — no checkout."),
    CommandGroup(
        path="transpile", help="An e-nous core into each harness, from its specs — and back, to see what moved."
    ),
    CommandGroup(
        path="workflow", help="Corpus workflows: graphs of command and agent steps, run from an e-nous checkout."
    ),
    CommandGroup(
        path="workflow soa-assess",
        help="soa-assess's deterministic steps, one per workflow node: --rundir, --nous.",
        show=False,
    ),
    CommandGroup(
        path="workflow soa-compare",
        help="soa-compare's deterministic steps, one per workflow node: --rundir, --nous.",
        show=False,
    ),
    CommandGroup(
        path="workflow soa-sweep",
        help="soa-sweep's deterministic steps, one per workflow node: --nous, --rundir.",
        show=False,
    ),
    CommandGroup(
        path="workflow reverse-distill",
        help="reverse-distill's deterministic steps, one per workflow node: --nous, --rundir.",
        show=False,
    ),
    CommandGroup(
        path="eval", help="The evaluator: measure a corpus target, read-only; every subject ends in its needs."
    ),
    CommandGroup(
        path="enhance", help="The enhancer: act on a reason in a sandbox; verdicts, patches, a human promotes."
    ),
    CommandGroup(path="reports", help="Evaluation and enhancement runs, rebuilt from their ledgers."),
    CommandGroup(path="schedule", help="Unattended runs: the core's schedules as systemd user timers taxis-<id>."),
)

CARDS: tuple[CommandCard, ...] = (
    CommandCard(
        path="map", target="e_taxis.harness.commands.catalog:mapping", summary="The catalog, per target and profile."
    ),
    CommandCard(
        path="plan", target="e_taxis.harness.commands.stack:plan", summary="What apply would do; writes nothing."
    ),
    CommandCard(
        path="verify", target="e_taxis.harness.commands.stack:verify", summary="Run every wanted part's verify."
    ),
    CommandCard(
        path="doctor", target="e_taxis.harness.commands.catalog:doctor", summary="Check the catalog's integrity."
    ),
    CommandCard(
        path="apply", target="e_taxis.harness.commands.install:apply", summary="Carry the plan out; dry unless --yes."
    ),
    CommandCard(
        path="install",
        target="e_taxis.harness.commands.install:install",
        summary="Brain, then systems; dry unless --yes.",
    ),
    CommandCard(
        path="uninstall",
        target="e_taxis.harness.commands.install:uninstall",
        summary="Take one part out; dry unless --yes.",
    ),
    CommandCard(path="history list", target="e_taxis.harness.commands.history:listing", summary="Every recorded run."),
    CommandCard(
        path="history undo", target="e_taxis.harness.commands.history:undo", summary="Revert the last recorded run."
    ),
    CommandCard(
        path="transpile check",
        target="e_taxis.transpile.commands.transpile:check",
        summary="Hold a checkout to its schema and every spec's law.",
    ),
    CommandCard(
        path="transpile run",
        target="e_taxis.transpile.commands.transpile:run",
        summary="Project a core for one backend; --out for a pure export.",
    ),
    CommandCard(
        path="transpile reverse",
        target="e_taxis.transpile.commands.transpile:reverse",
        summary="Read the live tree back: who moved each fragment since the last landing.",
    ),
    CommandCard(
        path="transpile trial",
        target="e_taxis.transpile.commands.transpile:trial",
        summary="Raise the real harness fenced on the render; check what it loaded.",
    ),
    CommandCard(
        path="workflow run",
        target="e_taxis.workflow.commands.workflow:run",
        summary="Run a workflow; exits 24 when a step failed.",
    ),
    CommandCard(
        path="workflow step",
        target="e_taxis.workflow.commands.workflow:step",
        summary="Run one step inside a run a harness walks; one JSON line.",
    ),
    CommandCard(
        path="workflow put",
        target="e_taxis.workflow.commands.workflow:put",
        summary="Keep a harness agent's answer as a semantic step's out.",
    ),
    CommandCard(
        path="workflow list",
        target="e_taxis.workflow.commands.workflow:listing",
        summary="Every workflow drawn: parameters, then D/S step chains.",
    ),
    CommandCard(
        path="workflow check",
        target="e_taxis.workflow.commands.workflow:check",
        summary="Hold workflows to their static law; writes nothing.",
    ),
    CommandCard(
        path="workflow soa-compare intake",
        target="e_taxis.workflow.commands.compare:intake",
        summary="Read the repository's declared stack and imports.",
    ),
    CommandCard(
        path="workflow soa-compare health",
        target="e_taxis.workflow.commands.compare:health",
        summary="Health and hot-path language of every subject.",
    ),
    CommandCard(
        path="workflow soa-compare rank",
        target="e_taxis.workflow.commands.compare:rank",
        summary="Score on one rubric; shortlist the rivals that win.",
    ),
    CommandCard(
        path="workflow soa-compare bench",
        target="e_taxis.workflow.commands.compare:bench",
        summary="Bench every shortlisted pair, fenced.",
    ),
    CommandCard(
        path="workflow soa-compare stats",
        target="e_taxis.workflow.commands.compare:stats",
        summary="Every pair's interval against its threshold.",
    ),
    CommandCard(
        path="workflow soa-compare report",
        target="e_taxis.workflow.commands.compare:report",
        summary="Write report.md and compare.json; index the verdicts.",
    ),
    CommandCard(
        path="workflow soa-compare schemas",
        target="e_taxis.workflow.commands.compare:schemas",
        summary="Write (or --check) every soa-compare port's JSON Schema.",
    ),
    CommandCard(
        path="workflow soa-assess intake",
        target="e_taxis.workflow.commands.assess:intake",
        summary="Resolve a technology to its repository and package.",
    ),
    CommandCard(
        path="workflow soa-assess inventory",
        target="e_taxis.workflow.commands.assess:inventory",
        summary="What lives here in the candidate's domain, no model.",
    ),
    CommandCard(
        path="workflow soa-assess health",
        target="e_taxis.workflow.commands.assess:health",
        summary="Dated health KPIs from no-auth sources.",
    ),
    CommandCard(
        path="workflow soa-assess bench",
        target="e_taxis.workflow.commands.assess:bench",
        summary="Install every arm fenced; run the plan interleaved.",
    ),
    CommandCard(
        path="workflow soa-assess stats",
        target="e_taxis.workflow.commands.assess:stats",
        summary="The paired bootstrap interval against the threshold.",
    ),
    CommandCard(
        path="workflow soa-assess report",
        target="e_taxis.workflow.commands.assess:report",
        summary="Write report.md and assess.json; index the verdict.",
    ),
    CommandCard(
        path="workflow soa-assess schemas",
        target="e_taxis.workflow.commands.assess:schemas",
        summary="Write (or --check) every soa-assess port's JSON Schema.",
    ),
    CommandCard(
        path="workflow soa-sweep frame",
        target="e_taxis.workflow.commands.sweep:frame",
        summary="Fix the frame from soa.yaml; an unknown topic fails here.",
    ),
    CommandCard(
        path="workflow soa-sweep ledger",
        target="e_taxis.workflow.commands.sweep:ledger",
        summary="The seen ledger, for the frame's voices.",
    ),
    CommandCard(
        path="workflow soa-sweep fetch",
        target="e_taxis.workflow.commands.sweep:fetch",
        summary="Every voice and entry page inside the window.",
    ),
    CommandCard(
        path="workflow soa-sweep ground",
        target="e_taxis.workflow.commands.sweep:ground",
        summary="Merge the findings; keep what a fetched page holds.",
    ),
    CommandCard(
        path="workflow soa-sweep fit",
        target="e_taxis.workflow.commands.sweep:fit",
        summary="Mark each finding have, considered or new.",
    ),
    CommandCard(
        path="workflow soa-sweep report",
        target="e_taxis.workflow.commands.sweep:report",
        summary="Write report.md and report.json; record the ledger.",
    ),
    CommandCard(
        path="workflow soa-sweep deliver",
        target="e_taxis.workflow.commands.sweep:deliver",
        summary="Post the summary and report.md to Discord.",
    ),
    CommandCard(
        path="workflow soa-sweep schemas",
        target="e_taxis.workflow.commands.sweep:schemas",
        summary="Write (or --check) every soa-sweep port's JSON Schema.",
    ),
    CommandCard(
        path="workflow reverse-distill guard",
        target="e_taxis.workflow.commands.distill:guard",
        summary="Fix the scope; exit 3 when nothing is past the base.",
    ),
    CommandCard(
        path="workflow reverse-distill intake",
        target="e_taxis.workflow.commands.distill:intake",
        summary="The range's commits and touched files.",
    ),
    CommandCard(
        path="workflow reverse-distill index",
        target="e_taxis.workflow.commands.distill:index",
        summary="e-nous, e-arkhetypo and the project into the code graph.",
    ),
    CommandCard(
        path="workflow reverse-distill scan",
        target="e_taxis.workflow.commands.distill:scan",
        summary="The range's changed files and impacted symbols.",
    ),
    CommandCard(
        path="workflow reverse-distill drift",
        target="e_taxis.workflow.commands.distill:drift",
        summary="The project's own drift checks, read.",
    ),
    CommandCard(
        path="workflow reverse-distill inventory",
        target="e_taxis.workflow.commands.distill:inventory",
        summary="Every plane, without a model: what the cores do not say.",
    ),
    CommandCard(
        path="workflow reverse-distill grade",
        target="e_taxis.workflow.commands.distill:grade",
        summary="Merge the miners, propagate contradictions, weigh.",
    ),
    CommandCard(
        path="workflow reverse-distill report",
        target="e_taxis.workflow.commands.distill:report",
        summary="Join verdicts and reviews; write report.md and briefs.",
    ),
    CommandCard(
        path="workflow reverse-distill ship",
        target="e_taxis.workflow.commands.distill:ship",
        summary="Run the commands that apply the musts.",
    ),
    CommandCard(
        path="workflow reverse-distill schemas",
        target="e_taxis.workflow.commands.distill:schemas",
        summary="Write (or --check) every port's JSON Schema.",
    ),
    CommandCard(
        path="eval run",
        target="e_taxis.workflow.commands.eval:run",
        summary="Measure a target's subjects; exits 24 only when a node broke.",
    ),
    CommandCard(
        path="eval graph",
        target="e_taxis.workflow.commands.eval:graph",
        summary="Print and prove the evaluator's graphs.",
    ),
    CommandCard(
        path="eval needs",
        target="e_taxis.workflow.commands.eval:needs",
        summary="An evaluation's open needs; exits 1 while any is open.",
    ),
    CommandCard(
        path="enhance run",
        target="e_taxis.workflow.commands.enhance:run",
        summary="Enhance on a reason, in a sandbox; verdicts and patches.",
    ),
    CommandCard(
        path="enhance graph",
        target="e_taxis.workflow.commands.enhance:graph",
        summary="Print and prove the enhancer's graphs.",
    ),
    CommandCard(
        path="enhance promote",
        target="e_taxis.workflow.commands.enhance:promote",
        summary="Apply an enhancement's patches to the checkout; a human command.",
    ),
    CommandCard(
        path="reports show",
        target="e_taxis.workflow.commands.reports:show",
        summary="A plane run's report, rebuilt from its ledger.",
    ),
    CommandCard(
        path="schedule list",
        target="e_taxis.schedule.commands.schedule:listing",
        summary="Every schedule with its timer's state; orphans too.",
    ),
    CommandCard(
        path="schedule apply",
        target="e_taxis.schedule.commands.schedule:apply",
        summary="Render the schedules into systemd user timers; dry unless --yes.",
    ),
    CommandCard(
        path="schedule run",
        target="e_taxis.schedule.commands.schedule:run",
        summary="Run one now through systemd; exits 33 unless it succeeds.",
    ),
    CommandCard(path="logo", target="e_taxis.ops.logo:logo", summary="Deterministic family wordmarks into assets/."),
    CommandCard(path="repo resolve", target="e_taxis.ops.repo:resolve", summary="The commit a ref names on a remote."),
    CommandCard(path="repo tree", target="e_taxis.ops.repo:tree", summary="Every file under a path at a ref."),
    CommandCard(
        path="repo extract", target="e_taxis.ops.repo:extract", summary="Unpack a path at a ref into a directory."
    ),
)


def build() -> App:
    """Composition root: the tree from the tables, the launcher on the meta app. Imports no command module."""
    root = App(
        name="taxis",
        help="e-taxis — mounts agent harnesses after the transpile",
        version=version("e-taxis"),
        result_action="return_value",
    )
    apps = {"": root}
    for group in GROUPS:
        apps[group.path] = App(name=group.name, help=group.help, show=group.show)
        apps[group.parent].command(apps[group.path])
    for card in CARDS:
        apps[card.parent].command(card.target, name=card.name, help=card.summary)
    root.meta.default(Launcher(root, CARDS).run)
    return root


def main() -> None:
    """The `taxis` script: build, run, exit with the launcher's code."""
    sys.exit(build().meta(sys.argv[1:]))
