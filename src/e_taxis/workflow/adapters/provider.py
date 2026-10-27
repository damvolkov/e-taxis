"""adapters.provider: a house tier resolved to its endpoint, from the e-nous checkout's models config alone.

`core/tekton/config/models.yaml` names, per tier, `<alias>/<model>`; the alias is a provider with its base URL, its
OpenAI-compatible twin and `api_key` — a literal, or `{env:NAME}`, the variable holding the secret. This is the one
place that variable is read, from the environment the adapter was built with."""

import re
from typing import TYPE_CHECKING, Any, Final

import anyio
import eserde

from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.error import ProviderError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

##### DEFAULTS #####
MODELS: str = "core/tekton/config/models.yaml"
SECRET: Final[re.Pattern[str]] = re.compile(r"^\{env:([A-Za-z0-9_]+)\}$")


##### TYPES #####
class HouseProvider:
    """Satisfies ProviderPort over a checkout's models config and an environment."""

    __slots__ = ("_environ",)

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = environ

    ##### PRIVATE METHODS #####

    def _endpoint_key(self, raw: str) -> str:
        """The key a provider declares: the literal, or the value of the variable it names."""
        match SECRET.match(raw):
            case None:
                return raw
            case found if (value := self._environ.get(found.group(1))) is not None:
                return value
            case found:
                msg = f"{found.group(1)} is not set in the environment"
                raise ProviderError(msg)

    ############################################################

    ##### PUBLIC #####

    async def endpoint(self, nous: Path, tier: str) -> Endpoint:
        """`scout` → its provider's base URL, the key, the model name after the alias."""
        models: dict[str, Any] = eserde.loads(await anyio.Path(nous / MODELS).read_text(), format=eserde.Format.YAML)
        match (models.get("tiers") or {}).get(tier):
            case {"model": str() as route} if provider := (models.get("providers") or {}).get(route.split("/")[0]):
                return Endpoint(
                    base_url=provider["base_url"],
                    key=self._endpoint_key(str(provider.get("api_key", ""))),
                    model=route.split("/", 1)[1],
                    openai_url=provider.get("openai_url", ""),
                )
            case _:
                msg = f"tier {tier!r} resolves to no provider in {nous / MODELS}"
                raise ProviderError(msg)
