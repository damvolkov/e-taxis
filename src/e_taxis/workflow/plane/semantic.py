"""plane.semantic: the security scan with SkillSpector's LLM stage on — its semantic analyzers (intent, quality policy,
security discovery) and the meta-analyzer that weeds out the static stage's false positives — on the house tier
`TAXIS_EVAL_SEMANTIC_TIER`, through the provider's OpenAI-compatible twin. The same placing in core/ and the same
accepted findings as `security`; it costs tokens and reads stochastically, so it measures weekly and gates nothing."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from e_taxis.workflow.models.plane import Cadence, Nature, NodeCard, Role
from e_taxis.workflow.plane.security import PlaneSecurity

if TYPE_CHECKING:
    from e_taxis.workflow.models.endpoint import Endpoint
    from e_taxis.workflow.models.ports import PlaneContext, ProviderPort, ScannerPort


##### TYPES #####
class PlaneSemantic(PlaneSecurity):
    """Satisfies PlaneNodePort: `security`, its LLM stage on the endpoint `provider` resolves `tier` to."""

    __slots__ = ("_provider", "_tier")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.MEASURE,
        summary="SkillSpector with its LLM stage on the house provider; findings in core/, accepted ones dropped",
        nature=Nature.HEURISTIC,
        cadence=(Cadence.WEEKLY,),
    )

    def __init__(self, scanner: ScannerPort, fail: str, provider: ProviderPort, tier: str) -> None:
        super().__init__(scanner, fail)
        self._provider = provider
        self._tier = tier

    ##### PRIVATE METHODS #####

    async def _run_llm(self, context: PlaneContext) -> Endpoint | None:
        return await self._provider.endpoint(Path(context.state.manifest.nous), self._tier)
