"""plane.integrate: the one writer of an enhancement — the house `integrator` folds every source's lessons into the
subject itself, or discards each with its reason.

Lessons come from the sources `params.sources` names (`brief` by default). The session runs in a private clone of the
run's sandbox holding the subject as the sandbox has it; git measures what it touched there, and only the subject's
place returns to the sandbox — never a refused session's. A session is refused when it wrote the real checkout,
wrote outside its subject, or — for a skill — created a file or touched `skill.yaml` (the description has its own
owner). The agent is the live tree's (`OpencodeAgent`, W1): v1 drove a render of the working tree; a workflow acts on
the applied corpus, and so does this proposer."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

import anyio

from e_taxis.workflow.models.metrics import ProposalMetrics
from e_taxis.workflow.models.plane import Guard, Nature, NodeCard, Role, Target
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import AgentPort, PlaneContext, SandboxPort

##### DEFAULTS #####
AGENT: str = "integrator"
BRIEF: Final[str] = """\
Integrate into the {kind} `{subject}` ({place}/) the lessons below; they are your only input.
Follow your prompt and flow-gen-lifecycle: fold each lesson where the {kind} already governs
its concept, or discard it with its reason. Never append a block, never write outside {place}/.{extra}

Lessons:
{lessons}
{excerpts}"""
### a place a lesson names: a core/ file and its line.
PLACE: Final[re.Pattern[str]] = re.compile(r"(core/[\w./-]+\.(?:md|yaml)):(\d+)")
SPAN: int = 8
SKILL: str = " Never create a file, never touch skill.yaml."
MANIFEST: str = "skill.yaml"
NOTHING: str = "no lesson from any source"


##### TYPES #####
class PlaneIntegrate:
    """Satisfies PlaneNodePort over an agent and the sandbox; `limit` bounds one session."""

    __slots__ = ("_agent", "_limit", "_sandbox")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.PROPOSE,
        summary="the integrator agent folds every source's lessons into the subject itself",
        nature=Nature.SEMANTIC,
        guard=Guard.SETTLED,
    )

    def __init__(self, agent: AgentPort, sandbox: SandboxPort, limit: float) -> None:
        self._agent = agent
        self._sandbox = sandbox
        self._limit = limit

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_lessons(context: PlaneContext) -> tuple[str, ...]:
        found = [
            lesson
            for source in context.param("sources", "brief").split(",")
            if (row := context.upstream(source)) and isinstance(row.metrics, ProposalMetrics)
            for lesson in row.metrics.lessons
        ]
        return tuple(dict.fromkeys(found))

    @staticmethod
    async def _run_excerpt(sandbox: Path, path: str, line: int) -> str:
        file = anyio.Path(sandbox / path)
        lines = (await file.read_text()).splitlines() if await file.is_file() else []
        shown = "\n".join(f"{n:>4}  {text}" for n, text in enumerate(lines, 1) if abs(n - line) <= SPAN)
        return f"### {path}:{line}\n```\n{shown}\n```" if lines else ""

    @classmethod
    async def _run_excerpts(cls, sandbox: Path, lessons: tuple[str, ...]) -> str:
        """The lines each lesson names, read from the sandbox: the integrator starts where it must act."""
        places = dict.fromkeys((path, int(line)) for lesson in lessons for path, line in PLACE.findall(lesson))
        blocks = [block for path, line in places if (block := await cls._run_excerpt(sandbox, path, line))]
        head = "\nWhere they land (read further only if folding the lesson needs it):\n\n"
        return f"{head}{'\n\n'.join(blocks)}\n" if blocks else ""

    @staticmethod
    def _run_refused(
        place: str, *, skill: bool, touched: list[str], created: list[str], real: tuple[str, ...]
    ) -> list[str]:
        """Why a session is refused: it wrote the real checkout, outside its subject, the manifest, or a new file."""
        return [
            *([f"wrote into the real checkout ({len(real)} dirty paths)"] if real else []),
            *(f"wrote outside {place}/: {path}" for path in touched if not path.startswith(f"{place}/")),
            *(f"touched the description's manifest: {path}" for path in touched if skill and path.endswith(MANIFEST)),
            *(f"created a file: {path}" for path in created),
        ]

    async def _run_session(self, context: PlaneContext, lessons: tuple[str, ...]) -> Outcome:
        state = context.state
        manifest, paths = state.manifest, state.paths
        place, skill, nous = manifest.place(context.subject), manifest.target is Target.SKILL, Path(manifest.nous)
        brief = BRIEF.format(
            kind=manifest.target.value,
            subject=context.subject,
            place=place,
            extra=SKILL if skill else "",
            lessons="\n".join(f"- {lesson}" for lesson in lessons),
            excerpts=await self._run_excerpts(paths.sandbox, lessons),
        )
        tree = await self._sandbox.open(paths.sandbox, context.workdir / "tree", manifest.base_sha)
        try:
            await self._sandbox.overlay(paths.sandbox, tree, place)
            (real, _), (_, own) = await self._sandbox.fingerprint(nous), await self._sandbox.fingerprint(tree)
            existed = set(await self._sandbox.created(tree, place))
            reply = await self._agent.drive(AGENT, brief, cwd=tree, limit=self._limit)
            (moved, dirty), (_, wrote) = await self._sandbox.fingerprint(nous), await self._sandbox.fingerprint(tree)
            created = sorted(set(await self._sandbox.created(tree, place)) - existed) if skill else []
            touched = sorted(path for path in wrote.keys() | own.keys() if wrote.get(path) != own.get(path))
            refused = self._run_refused(
                place, skill=skill, touched=touched, created=created, real=tuple(dirty) if moved != real else ()
            )
            _ = refused or await self._sandbox.overlay(tree, paths.sandbox, place)
        finally:
            await self._sandbox.close(tree)
        session = context.workdir / "session.md"
        await anyio.Path(session).write_text(reply.text)
        return Outcome(
            status=Status.FAIL if refused else Status.OK,
            metrics=ProposalMetrics(
                proposer=AGENT, files=tuple(path for path in touched if path.startswith(f"{place}/")), lessons=lessons
            ),
            tokens=reply.tokens,
            cached=reply.cached,
            runner="opencode",
            reason="; ".join(refused),
            artifacts=(str(session),),
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        match self._run_lessons(context):
            case ():
                return Outcome(status=Status.IDLE, reason=NOTHING)
            case lessons:
                await anyio.Path(context.workdir).mkdir(parents=True, exist_ok=True)
                return await self._run_session(context, lessons)
