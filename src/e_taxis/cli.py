"""e-taxis entrypoint: `taxis` — the command tree is two tables, and nothing under commands/ loads until it runs.

`GROUPS` and `CARDS` are the whole surface. `build` is the composition root: it turns the tables into
cyclopts apps and mounts every card by its `module:function` string, so importing this module imports no
command, and `taxis --help` or any group listing is served from the cards alone. The meta app runs the
`Launcher` first on every call: global options, the run's lifespan, injection by type, the error boundary.

Adding a command is one row in `CARDS` plus one plain function; a command that needs a new group adds a
row in `GROUPS`, parents before children. `tests/unit/e_taxis/test_cli.py` resolves every target, so a
typo fails the gate, never a user.

    taxis map      [--target T] [--json]
    taxis plan     --target T (--profile P | --nous PATH) [--json]
    taxis verify   --target T (--profile P | --nous PATH) [--json]
    taxis doctor   [--json]
    taxis install  --target T --nous PATH [--profile P] [--ref REF | --worktree] [--yes]
                   [--accept-licence ID] [--confirm ID] [--json]
    taxis apply    --target T (--profile P | --nous PATH) [--only id,...] [--dry-run] [--yes]
                   [--accept-licence ID] [--confirm ID] [--json]
    taxis uninstall ID --target T [--cascade] [--yes]
    taxis history  list · undo
    taxis transpile check --nous PATH [--ref REF | --worktree] [--json]   # schema + spec law; writes nothing
    taxis transpile run   --target T --nous PATH --out DIR [--ref REF | --worktree] [--json]   # pure export
    taxis workflow run ID --nous PATH [name=value ...]                  # a corpus workflow, end to end
    taxis workflow list --nous PATH · check [ID ...] --nous PATH
    taxis distill guard|intake|index|scan|drift|inventory|grade|report|ship|schemas --nous PATH --rundir DIR …
    taxis eval run TARGET [IDS ...] --nous PATH [--cadence C] [--candidate RUN]   # the evaluator, read-only
    taxis eval graph [TARGET] · eval needs TARGET --nous PATH [--run R] [--owner O]
    taxis enhance run TARGET [IDS ...] --nous PATH (--from R | --directive D | --manual) [--cadence C]
    taxis enhance graph [TARGET] · enhance promote [RUN] --nous PATH [--ids ...] [--all-verdicts] [--yes]
    taxis reports show [RUN] --nous PATH [--json]
    taxis logo NAMES [--out DIR] [--prefix P] [--background HEX] [--foreground HEX] [--force]
    taxis repo resolve URL REF                     # the commit a branch, tag or sha names
    taxis repo tree    URL REF [PATH]              # every file the remote holds at REF
    taxis repo extract URL REF PATH --dest DIR     # unpack it; `make core` uses exactly this
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
        path="distill", help="reverse-distill's deterministic steps, one per workflow node: --nous, --rundir."
    ),
    CommandGroup(path="eval", help="The evaluator: measure a corpus target, read-only; every subject ends in its needs."),
    CommandGroup(path="enhance", help="The enhancer: act on a reason in a sandbox; verdicts, patches, a human promotes."),
    CommandGroup(path="reports", help="Evaluation and enhancement runs, rebuilt from their ledgers."),
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
        path="workflow list",
        target="e_taxis.workflow.commands.workflow:listing",
        summary="Every workflow, its parameters and steps.",
    ),
    CommandCard(
        path="workflow check",
        target="e_taxis.workflow.commands.workflow:check",
        summary="Hold workflows to their static law; writes nothing.",
    ),
    CommandCard(
        path="distill guard",
        target="e_taxis.workflow.commands.distill:guard",
        summary="Fix the scope; exit 3 when nothing is past the base.",
    ),
    CommandCard(
        path="distill intake",
        target="e_taxis.workflow.commands.distill:intake",
        summary="The range's commits and touched files.",
    ),
    CommandCard(
        path="distill index",
        target="e_taxis.workflow.commands.distill:index",
        summary="e-nous, e-arkhetypo and the project into the code graph.",
    ),
    CommandCard(
        path="distill scan",
        target="e_taxis.workflow.commands.distill:scan",
        summary="The range's changed files and impacted symbols.",
    ),
    CommandCard(
        path="distill drift",
        target="e_taxis.workflow.commands.distill:drift",
        summary="The project's own drift checks, read.",
    ),
    CommandCard(
        path="distill inventory",
        target="e_taxis.workflow.commands.distill:inventory",
        summary="Every plane, without a model: what the cores do not say.",
    ),
    CommandCard(
        path="distill grade",
        target="e_taxis.workflow.commands.distill:grade",
        summary="Merge the miners, propagate contradictions, weigh.",
    ),
    CommandCard(
        path="distill report",
        target="e_taxis.workflow.commands.distill:report",
        summary="Join verdicts and reviews; write report.md and briefs.",
    ),
    CommandCard(
        path="distill ship",
        target="e_taxis.workflow.commands.distill:ship",
        summary="Run the commands that apply the musts.",
    ),
    CommandCard(
        path="distill schemas",
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
        apps[group.path] = App(name=group.name, help=group.help)
        apps[group.parent].command(apps[group.path])
    for card in CARDS:
        apps[card.parent].command(card.target, name=card.name, help=card.summary)
    root.meta.default(Launcher(root, CARDS).run)
    return root


def main() -> None:
    """The `taxis` script: build, run, exit with the launcher's code."""
    sys.exit(build().meta(sys.argv[1:]))
