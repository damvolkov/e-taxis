"""plane.law: the house law over one subject, on the base or on its candidate (`tree=base|candidate`).

A skill is judged on its render — the SKILL.md that reaches the context window and its references — under
`skills/<id>/` of the flat tree; an agent or a command on its core manifest, against what that tree holds (skills,
agents, MCP servers, model tiers); a spec by the v2 transpiler's own law (`CheckService`: its blocking findings for
that backend). A kind with no law of its own is a plain green. The base is the tree under measure (and its render);
a candidate is the subject's own tree under `trees/<id>/` (and its render)."""

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

import anyio
import eserde

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.engine.law import RULE, AgentLaw, CommandLaw, SkillLaw, front_law
from e_taxis.workflow.models.metrics import LawMetrics
from e_taxis.workflow.models.plane import NodeCard, Role, Target
from e_taxis.workflow.models.run import Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.services.check import CheckService
    from e_taxis.workflow.models.ports import PlaneContext

##### DEFAULTS #####
CANDIDATE: str = "candidate"
BASE: str = "base"
FACET: str = "tekton"
SKILLS: str = "skills"
REFERENCES: str = "references"
MANIFEST: str = "command.yaml"


##### UTILITIES #####
def tiers_of(tree: NousTree) -> frozenset[str]:
    return frozenset(tree.config.get(FACET, {}).get("models", {}).get("tiers", {}))


def servers_of(tree: NousTree) -> frozenset[str]:
    return frozenset(tree.config.get(FACET, {}).get("mcp", {}).get("servers", {}))


##### TYPES #####
class PlaneLaw:
    """Satisfies PlaneNodePort: one law per target kind, a frozen table; the v2 check for a spec."""

    __slots__ = ("_checker",)

    card: ClassVar[NodeCard] = NodeCard(role=Role.GATE, summary="house law over the base or the candidate")

    def __init__(self, checker: CheckService) -> None:
        self._checker = checker

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_source(context: PlaneContext) -> Path:
        """The source tree the law reads: the subject's candidate tree, or the tree under measure."""
        state = context.state
        return (
            state.paths.tree(context.subject) if context.param("tree", BASE) == CANDIDATE else Path(state.manifest.tree)
        )

    @staticmethod
    def _run_flat(context: PlaneContext) -> Path:
        paths = context.state.paths
        return paths.candidate(context.subject) if context.param("tree", BASE) == CANDIDATE else paths.base

    async def _law_skill(self, context: PlaneContext) -> Outcome:
        tree = context.param("tree", BASE)
        folder = anyio.Path(self._run_flat(context) / SKILLS / context.subject)
        match await (folder / "SKILL.md").is_file():
            case False:
                return Outcome(status=Status.SKIP, reason=f"no {tree} render of {context.subject}")
            case _:
                text = await (folder / "SKILL.md").read_text()
        references = {path.name: await path.read_text() async for path in (folder / REFERENCES).glob("*.md")}
        violations = SkillLaw.check(context.subject, text, references)
        description = front_law(text).get("description", "").strip().strip('"')
        return Outcome(
            status=Status.FAIL if violations else Status.OK,
            metrics=LawMetrics(
                tree=tree,
                violations=violations,
                lines=len(text.splitlines()),
                rules=len(RULE.findall(text)),
                description=len(description),
            ),
        )

    async def _law_agent(self, context: PlaneContext) -> Outcome:
        tree = await GitNous(self._run_source(context), None).load()
        violations = AgentLaw.check(
            tree.entities["agent"][context.subject],
            agents=frozenset(tree.entities.get("agent", {})),
            skills=frozenset(tree.entities.get("skill", {})),
            servers=servers_of(tree),
            tiers=tiers_of(tree),
        )
        return self._common_outcome(context, violations)

    async def _law_command(self, context: PlaneContext) -> Outcome:
        source = self._run_source(context)
        tree = await GitNous(source, None).load()
        place = context.state.manifest.place(context.subject)
        raw: Mapping[str, Any] = eserde.loads(
            await anyio.Path(source / place / MANIFEST).read_text(), format=eserde.Format.YAML
        )
        violations = CommandLaw.check(
            raw,
            folder=context.subject,
            template=str(tree.entities["command"][context.subject].get("template", "")),
            agents=frozenset(tree.entities.get("agent", {})),
            skills=frozenset(tree.entities.get("skill", {})),
            tiers=tiers_of(tree),
        )
        return self._common_outcome(context, violations)

    async def _law_spec(self, context: PlaneContext) -> Outcome:
        report = await self._checker.run(GitNous(self._run_source(context), None))
        violations = tuple(
            f"{finding.kind} {finding.where} {finding.path}: {finding.detail}".strip()
            for finding in report.blocking
            if finding.backend == context.subject
        )
        return self._common_outcome(context, violations)

    async def _law_none(self, context: PlaneContext) -> Outcome:
        return self._common_outcome(context, ())

    @staticmethod
    def _common_outcome(context: PlaneContext, violations: tuple[str, ...]) -> Outcome:
        return Outcome(
            status=Status.FAIL if violations else Status.OK,
            metrics=LawMetrics(tree=context.param("tree", BASE), violations=violations),
        )

    LAWS: ClassVar[Mapping[Target, Callable[[PlaneLaw, PlaneContext], Awaitable[Outcome]]]] = MappingProxyType(
        {
            Target.SKILL: _law_skill,
            Target.AGENT: _law_agent,
            Target.COMMAND: _law_command,
            Target.SPEC: _law_spec,
        }
    )

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        law = self.LAWS.get(context.state.manifest.target, PlaneLaw._law_none)
        return await law(self, context)
