"""commands.workflow: driving adapter for corpus workflows — `taxis workflow run | list | check --nous PATH`.

The workflows are data in an e-nous checkout (`core/tekton/workflows/<id>/`), read as the checkout stands. `run`
executes one: the live rows on stderr as each step lands, the report on stdout, and a non-zero exit (24) when any
step failed or broke — after the report, never instead of it. `list` shows every workflow with its parameters and
steps; `check` holds every workflow (or the ones named) to its static law and writes nothing."""

import sys

from rich.console import Console
from rich.markup import escape

from e_taxis.harness.runtime.deps import Inject
from e_taxis.harness.runtime.locator import UNSET, Nous
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.error import RunFailedError, WorkflowError
from e_taxis.workflow.models.graph import StepSpec
from e_taxis.workflow.models.run import NodeRun
from e_taxis.workflow.services.run import WorkflowRun


##### UTILITIES #####
def parse_params(param: tuple[str, ...]) -> dict[str, str]:
    """`name=value` tokens as a mapping; a token without `=` is refused."""
    match [token for token in param if "=" not in token]:
        case []:
            return dict(token.split("=", 1) for token in param)
        case bad:
            msg = f"parameters are name=value: {', '.join(bad)}"
            raise WorkflowError(msg)


def render_live(run: NodeRun) -> None:
    """One step, the moment the ledger records it — on stderr, so stdout stays the result."""
    reason = " ".join(run.reason.split())[:100]
    sys.stderr.write(f"  {run.node:<24}{run.status:<6}{run.seconds:>7.1f}s  {reason}\n")


def render_step(step: StepSpec) -> str:
    runner = "run" if step.run else step.actor or "lead"
    when = " · ".join(f"when {key}={'|'.join(values)}" for key, values in step.when.items())
    after = f"after {', '.join(step.depends)}" if step.depends else ""
    nature = "semantic" if step.semantic else "deterministic"
    return f"  {step.id:<18}{nature:<15}{runner:<20}{' · '.join(part for part in (when, after) if part)}".rstrip()


def render_workflow(reader: WorkflowReader, ident: str) -> str:
    """One workflow's card: parameters and steps — or why it does not read."""
    try:
        graph, decl = reader.read(ident)
    except WorkflowError as bad:
        return f"## {ident} — ✗ {bad.message}"
    params = [f"  param {name:<12}{param.doc}" for name, param in decl.params.items()]
    return "\n".join([f"## {ident} — {graph.summary[:100]}", *params, *(render_step(step) for step in graph)])


def check_workflow(reader: WorkflowReader, ident: str) -> tuple[bool, str]:
    """Whether one workflow reads clean, and why not."""
    try:
        reader.load(ident)
    except WorkflowError as bad:
        return False, bad.message
    return True, ""


##### COMMANDS #####
async def run(
    workflow: str, *param: str, nous: Nous = UNSET, runner: Inject[WorkflowRun], console: Inject[Console]
) -> None:
    """Run WORKFLOW from an e-nous checkout: command steps and agent steps, in parallel where the graph allows.

    Args:
        workflow: a workflow id under core/tekton/workflows/ (see `taxis workflow list`).
        param: name=value pairs for the workflow's declared parameters.
        nous: the e-nous checkout, read as it stands; its `.reports/` holds the run.
    """
    report = await runner.run(GitNous(nous, None), workflow, parse_params(param), render_live)
    console.out(report.markdown, highlight=False)
    console.out(f"→ {report.folder}/report.md", highlight=False)
    match report.broken:
        case ():
            pass
        case broken:
            msg = f"{len(broken)} step(s) failed: {', '.join(f'{run.node} ({run.status})' for run in broken)}"
            raise RunFailedError(msg)


async def listing(*, nous: Nous = UNSET, console: Inject[Console]) -> None:
    """List every workflow of an e-nous checkout with its parameters and steps.

    Args:
        nous: the e-nous checkout.
    """
    reader = WorkflowReader(await GitNous(nous, None).load())
    _ = [console.out(render_workflow(reader, ident), highlight=False) for ident in reader.ids()]


async def check(*workflow: str, nous: Nous = UNSET, console: Inject[Console]) -> None:
    """Hold every WORKFLOW (all when none is named) to its static law: steps, agents, hooks, ports, loop, cycles.

    Args:
        workflow: workflow ids under core/tekton/workflows/; all when omitted.
        nous: the e-nous checkout.
    """
    reader = WorkflowReader(await GitNous(nous, None).load())
    found = [(ident, *check_workflow(reader, ident)) for ident in workflow or reader.ids()]
    _ = [console.print(f"[red]✗[/] {escape(problem)}") for _, ok, problem in found if not ok]
    match [ident for ident, ok, _ in found if not ok]:
        case []:
            console.out(f"workflows: {len(found)} read clean", highlight=False)
        case bad:
            msg = f"{len(bad)} of {len(found)} workflow(s) do not read clean: {', '.join(bad)}"
            raise WorkflowError(msg)
