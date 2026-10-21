"""models.wanted: one part a source asks for — the id, which source named it, its pin if it has one."""

from msgspec import Struct


##### TYPES #####
class WantedPart(Struct, frozen=True, kw_only=True):
    """`source` is a label for the report: `profile:house`, `engineer:core/common/stack.yaml`, `requires:otel`."""

    id: str
    source: str
    pin: str | None = None
