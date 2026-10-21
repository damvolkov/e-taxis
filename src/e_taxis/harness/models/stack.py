"""models.stack: e-nous's stack registry, read as a foreign schema — only the fields e-taxis needs.

The registry is e-nous's document, not e-taxis's: it carries `what`, `link`, `wired`, `verify` and
more, and grows. Unknown fields are ignored here on purpose — the one place in e-taxis that does."""

from msgspec import Struct


##### TYPES #####
class StackPart(Struct, frozen=True, kw_only=True):
    """One part: its kind, its pin (empty: floating), the backends it serves."""

    kind: str
    pin: str = ""
    used: tuple[str, ...] = ()


class Stack(Struct, frozen=True, kw_only=True):
    """One `stack.yaml`: part id → part."""

    parts: dict[str, StackPart] = {}
