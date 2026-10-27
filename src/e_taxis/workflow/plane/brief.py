"""plane.brief: what the intake asks for, as lessons the integrator can place — your directive verbatim, every `law`
need as a fix to make, every `security` need as a finding to judge (rewrite what instructs harm, restructure what the
scanner could not read, leave what only names or forbids the threat; accepting a false positive is a human's, in
`security.yaml`). `routing` and `coverage` needs are reported unaddressed: the description has its own owner and the
case ledgers are written by hand."""

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final

from e_taxis.workflow.models.metrics import BriefMetrics, ProposalMetrics
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import NodeRun, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.workflow.models.ports import PlaneContext

##### DEFAULTS #####
### how each need kind the brief owns reads as a lesson; kinds absent here are another proposer's, or a human's.
LESSONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "law": "Fix the house law: {detail}",
        "security": (
            "Judge this security finding, then act on the core/ line it names. If the text instructs the agent to do "
            "what the rule fears, rewrite it safely. If the scanner could not read the text whole (an AE rule: partial "
            "analysis, parse limit, obfuscated text), restructure it for readability — shorter lines, plain prose. If "
            "the text only names, forbids or documents the threat, leave it as it is and say so in one line: never "
            "reword to dodge a scanner. Finding: {detail}"
        ),
    }
)
NOTHING: str = "no directive, no law or security need"


##### TYPES #####
class PlaneBrief:
    """Satisfies PlaneNodePort; reads only the intake."""

    __slots__ = ()

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.PROPOSE, summary="your directive, the law and the security needs, as lessons for the integrator"
    )

    async def run(self, context: PlaneContext) -> Outcome:
        match context.upstream("intake"):
            case NodeRun(metrics=BriefMetrics(directive=directive, needs=needs)):
                lessons = (
                    *((directive,) if directive else ()),
                    *(LESSONS[need.kind].format(detail=need.detail) for need in needs if need.kind in LESSONS),
                )
            case _:
                lessons = ()
        return Outcome(
            status=Status.OK if lessons else Status.IDLE,
            reason="" if lessons else NOTHING,
            metrics=ProposalMetrics(proposer="brief", files=(), lessons=lessons),
        )
