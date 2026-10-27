"""models.endpoint: where a house tier is served — what `core/tekton/config/models.yaml` resolves a tier to.

The config is the one place providers live (alias, base URL, the variable holding the key, the tiers naming a model
through an alias); every LLM call outside the coders asks for an `Endpoint`, so a provider or a key moves in one
file. `openai_url` is the provider's OpenAI-compatible twin, for tools with no Anthropic client (SkillSpector)."""

from msgspec import Struct


##### TYPES #####
class Endpoint(Struct, frozen=True, kw_only=True):
    """One tier's endpoint: the Messages API base, its key, the model name the API expects."""

    base_url: str
    key: str
    model: str
    openai_url: str = ""

    def __repr__(self) -> str:
        ### the key never reaches a log or a traceback.
        return f"Endpoint(base_url={self.base_url!r}, model={self.model!r})"
