"""models.entity: the kinds of thing an e-nous core holds — the vocabulary distill targets and the matrix grade."""

from enum import StrEnum


##### TYPES #####
class Entity(StrEnum):
    """One member per entity of `core/schema.yaml`; `persona` and `config` are singular, the rest one folder per id."""

    SKILL = "skill"
    AGENT = "agent"
    COMMAND = "command"
    WORKFLOW = "workflow"
    TOOL = "tool"
    PERSONA = "persona"
    CONFIG = "config"
