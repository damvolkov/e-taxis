"""services.step: one workflow step — a command, or an agent session; in a loop, its `until` check or an idle copy.

Every step may name its run: `{{run}}` its id, `{{rundir}}` its folder (where typed artifacts travel), `{{nous}}` the
e-nous checkout, `{{iteration}}` the loop copy it is. A command runs as `bash -lc` in the checkout, its parameters
bound as quoted variable references (`engine.bind`), never spliced into the script. Exit 3 is "nothing to do": the
step is a `skip`, and every step after it skips too, at zero tokens. An agent step is told the run so far: its id,
its folder and every ancestor's output."""

import graphlib
import hashlib
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, Final

import anyio

from e_taxis.workflow.engine.bind import ParamBind
from e_taxis.workflow.models.error import CommandError, NothingError, WorkflowError
from e_taxis.workflow.models.metrics import LoopMetrics, LoopState, SessionMetrics
from e_taxis.workflow.models.run import NodeRun, Outcome, Reply, Status

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.workflow.models.ports import AgentPort, CommandPort, NodeContext

##### DEFAULTS #####
### the lead's own agent: a step with an instruction and no actor is the lead acting directly.
LEAD: Final[str] = "orchestrator"
ECHO: str = "      ↳ "
TOLD: int = 4000
SAID: int = 20
REASON: int = 200
OPEN: int = 1
RUNNER: str = "bash"
AGENT: str = "opencode"


##### TYPES #####
class WorkflowStep:
    """Satisfies NodePort. `env` reaches every command a step runs (the run lock's token)."""

    __slots__ = ("_agent", "_command", "_env", "_limit")

    def __init__(self, command: CommandPort, agent: AgentPort, *, limit: float, env: Mapping[str, str]) -> None:
        self._command = command
        self._agent = agent
        self._limit = limit
        self._env = dict(env)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_params(context: NodeContext) -> dict[str, str]:
        manifest, spec = context.state.manifest, context.spec
        return manifest.params | {
            "iteration": str(spec.iteration) if spec.iteration else "",
            "run": manifest.run_id,
            "rundir": str(context.state.paths.root),
            "nous": manifest.nous,
        }

    @staticmethod
    def _run_ended(context: NodeContext) -> str:
        """The `until` check that ended this copy's loop, or empty while it runs on."""
        return next(
            (
                closer
                for closer in context.spec.closers
                if isinstance(metrics := getattr(context.upstream(closer), "metrics", None), LoopMetrics)
                and metrics.state.ends
            ),
            "",
        )

    @staticmethod
    def _run_ancestors(context: NodeContext) -> tuple[str, ...]:
        """Every step this one transitively waits on, in declaration order."""
        graph = context.state.manifest.graph
        parents = {step.id: step.depends for step in graph}
        closure = reduce(
            lambda found, ident: found | {ident: frozenset(parents[ident]).union(*(found[p] for p in parents[ident]))},
            graphlib.TopologicalSorter(parents).static_order(),
            {},
        )
        return tuple(step.id for step in graph if step.id in closure[context.spec.id])

    @staticmethod
    async def _run_told(context: NodeContext, step: str) -> str:
        out = anyio.Path(context.state.paths.out(step))
        match await out.is_file():
            case True:
                return f"### {step}\n{(await out.read_text())[-TOLD:]}"
            case _:
                row = context.upstream(step)
                said = f"{row.status}{f': {row.reason}' if row.reason else ''}" if row else "never ran"
                return f"### {step}\n{said}"

    async def _run_upstream(self, context: NodeContext) -> str:
        """What an agent step knows of its run: the run's id and every ancestor's output, or why it has none."""
        told = [await self._run_told(context, step) for step in self._run_ancestors(context)]
        run = context.state.manifest.run_id
        return f"Workflow run {run} — its folder is {context.state.paths.root}/.\n\n" + "\n\n".join(told)

    async def _run_command(self, context: NodeContext, params: Mapping[str, str]) -> Reply:
        command, variables = ParamBind.shell(context.spec.run, params)
        text = await self._command.run(
            "bash",
            "-lc",
            command,
            limit=float(context.spec.timeout or self._limit),
            cwd=Path(context.state.manifest.nous),
            env=self._env | variables,
            echo=ECHO,
        )
        return Reply(text=text)

    async def _run_agent(self, context: NodeContext, params: Mapping[str, str]) -> Reply:
        """The live tree's agent — a workflow acts on the applied corpus — in the checkout."""
        instruction = ParamBind.text(context.spec.instruction, params)
        prompt = f"{instruction}\n\nThis run so far:\n{await self._run_upstream(context)}"
        return await self._agent.drive(
            context.spec.actor or LEAD,
            prompt,
            cwd=Path(context.state.manifest.nous),
            limit=float(context.spec.timeout or self._limit),
            readonly=context.spec.readonly,
            steps=context.spec.steps,
        )

    async def _run_until(self, context: NodeContext, params: Mapping[str, str]) -> Outcome:
        """The loop's check: exit 0 closes it; exit 1 leaves it open — stalled when it says what the last check said."""
        try:
            said, code = (await self._run_command(context, params)).text, 0
        except CommandError as failed:
            match failed.code:
                case 1:
                    said, code = failed.stdout, OPEN
                case _:
                    return Outcome(status=Status.FAIL, runner=RUNNER, reason=str(failed)[:REASON])
        digest = hashlib.sha256(said.encode()).hexdigest()
        match context.upstream(context.spec.previous) if context.spec.previous else None:
            case NodeRun(metrics=LoopMetrics(digest=seen)):
                same = seen == digest
            case _:
                same = False
        state = LoopState.CLOSED if code == 0 else LoopState.STALLED if same else LoopState.OPEN
        lines = [line for line in said.splitlines() if line.strip()]
        out = context.state.paths.out(context.spec.id)
        await anyio.Path(out).write_text("\n".join(lines))
        return Outcome(
            status=Status.OK,
            runner=RUNNER,
            artifacts=(str(out),),
            reason=f"loop {state}",
            metrics=LoopMetrics(
                iteration=context.spec.iteration, state=state, open=len(lines) if code else 0, digest=digest
            ),
        )

    async def _run_step(self, context: NodeContext, params: Mapping[str, str]) -> Outcome:
        spec = context.spec
        try:
            reply = await (self._run_agent(context, params) if spec.semantic else self._run_command(context, params))
        except CommandError as failed:
            reply = Reply(text=str(failed))
            status = Status.SKIP if failed.code == NothingError.exit_code else Status.FAIL
        else:
            status = Status.OK
        out = context.state.paths.out(spec.id)
        await anyio.Path(out).write_text(reply.text)
        lines = tuple(line for line in reply.text.splitlines() if line.strip())[-SAID:]
        return Outcome(
            status=status,
            tokens=reply.tokens,
            cached=reply.cached,
            runner=AGENT if spec.semantic else RUNNER,
            artifacts=(str(out),),
            reason=lines[-1][:REASON] if status is not Status.OK and lines else "",
            metrics=SessionMetrics(agent=(spec.actor or LEAD) if spec.semantic else "run", narrative=lines),
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: NodeContext) -> Outcome:
        params = self._run_params(context)
        await anyio.Path(context.workdir).mkdir(parents=True, exist_ok=True)
        match (ParamBind.due(context.spec.when, params), self._run_ended(context), context.spec.until):
            case (False, _, _):
                when = "; ".join(f"{key}={'|'.join(values)}" for key, values in context.spec.when.items())
                return Outcome(status=Status.IDLE, reason=f"not when {when}")
            case (_, str() as ended, _) if ended:
                return Outcome(status=Status.IDLE, reason=f"loop ended at {ended}")
            case (_, _, True):
                return await self._run_until(context, params)
            case _:
                return await self._run_step(context, params)


class AnsweredStep:
    """Satisfies NodePort: a semantic step a harness agent already answered — kept as the step's out, the way the
    engine keeps an agent's reply, so every downstream step reads it the same."""

    __slots__ = ("_answer",)

    def __init__(self, answer: Path) -> None:
        self._answer = answer

    ##### PUBLIC #####

    async def run(self, context: NodeContext) -> Outcome:
        spec = context.spec
        match spec.semantic:
            case False:
                msg = f"{spec.id} is a command step: `taxis workflow step` runs it"
                raise WorkflowError(msg)
            case _:
                pass
        text = await anyio.Path(self._answer).read_text()
        await anyio.Path(context.workdir).mkdir(parents=True, exist_ok=True)
        out = context.state.paths.out(spec.id)
        await anyio.Path(out).write_text(text)
        lines = tuple(line for line in text.splitlines() if line.strip())[-SAID:]
        return Outcome(
            status=Status.OK,
            runner=AGENT,
            artifacts=(str(out),),
            metrics=SessionMetrics(agent=spec.actor or LEAD, narrative=lines),
        )
