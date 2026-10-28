"""services.kwargs: the run's kwargs read out of `query` by a small model — only what the caller left unsaid.

A workflow may be called with nothing but `query`. Then the kwargs the caller did not give are asked of the first
tier that answers (the local model, then the cheap hosted one): a strict JSON Schema built from the workflow's own
declarations — a bool or an enum is a closed set, a topic one of soa.yaml's, a list an array — and every field
required, empty meaning *not stated*, so the model fills nothing by guess. What it answers goes through the same
typed bind as a hand-typed value; what the caller gave always wins. No query, or nothing left to fill: no call."""

from typing import TYPE_CHECKING, Any, Final

from e_taxis.workflow.models.error import ProviderError, WorkflowError
from e_taxis.workflow.models.workflow import ParamType

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from e_taxis.workflow.models.ports import ChatPort, ProviderPort
    from e_taxis.workflow.models.workflow import Param, Workflow

##### DEFAULTS #####
QUERY: Final[str] = "query"
BOOLS: Final[tuple[str, ...]] = ("", "true", "false")


##### TYPES #####
class WorkflowKwargs:
    """`tiers` in the order they are tried; the first that answers reads the query."""

    __slots__ = ("_chat", "_provider", "_tiers")

    def __init__(self, chat: ChatPort, provider: ProviderPort, tiers: Sequence[str]) -> None:
        self._chat = chat
        self._provider = provider
        self._tiers = tuple(tiers)

    ##### PRIVATE METHODS #####

    @staticmethod
    def _fill_field(param: Param, topics: Sequence[str]) -> dict[str, Any]:
        """One kwarg as a schema field: closed sets as enums with `""` for unstated, a list as an array."""
        match param.type:
            case ParamType.LIST:
                return {"type": "array", "items": {"type": "string"}}
            case ParamType.BOOL:
                return {"type": "string", "enum": list(BOOLS)}
            case ParamType.TOPIC:
                return {"type": "string", "enum": ["", *topics]}
            case _ if param.values:
                return {"type": "string", "enum": ["", *param.values]}
            case _:
                return {"type": "string"}

    @staticmethod
    def _fill_system(decl: Workflow, missing: Mapping[str, Param]) -> str:
        lines = "\n".join(f"- {name}: {param.doc}" for name, param in missing.items())
        purpose = " ".join(decl.description.split())
        return (
            f"You turn a request into the parameters of the workflow {decl.id} ({purpose}). Fill every field. A field "
            "the request does not state is an empty string or an empty list — never guess it. Copy names as the "
            f"request writes them.\n\nFields:\n{lines}"
        )

    async def _fill_ask(
        self,
        nous: Path,
        prompt: tuple[str, str],
        schema: Mapping[str, Any],
        tiers: tuple[str, ...],
        failures: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], int, str]:
        """The first of `tiers` that answers; every failure named when none does."""
        match tiers:
            case (tier, *rest):
                pass
            case _:
                msg = f"query could not be read: {'; '.join(failures)}"
                raise WorkflowError(msg)
        try:
            endpoint = await self._provider.endpoint(nous, tier)
            said, tokens = await self._chat.structured(endpoint, *prompt, schema)
        except ProviderError as down:
            return await self._fill_ask(nous, prompt, schema, tuple(rest), (*failures, f"{tier}: {down}"))
        return said, tokens, tier

    ############################################################

    ##### PUBLIC #####

    async def fill(
        self, decl: Workflow, given: dict[str, str], nous: Path, topics: Sequence[str]
    ) -> tuple[dict[str, str], str, int]:
        """`given` with what the query states filled in; the tier that read it and its tokens (`""`, 0 when no call)."""
        missing = {name: param for name, param in decl.params.items() if name != QUERY and name not in given}
        query = given.get(QUERY, "")
        match (query, bool(missing)):
            case ("", _) | (_, False):
                return given, "", 0
            case _:
                pass
        schema = {
            "type": "object",
            "required": list(missing),
            "additionalProperties": False,
            "properties": {name: self._fill_field(param, topics) for name, param in missing.items()},
        }
        said, tokens, tier = await self._fill_ask(nous, (self._fill_system(decl, missing), query), schema, self._tiers)
        read = {
            name: " ".join(value) if isinstance(value, list) else str(value)
            for name, value in said.items()
            if name in missing and value not in ("", [], None)
        }
        return {**read, **given}, tier, tokens
