"""transforms.backends: which backends a core entry reaches — the one rule every `backends` field of the core obeys."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


##### UTILITIES #####
def reaches(entry: Mapping[str, Any] | str, backend: str) -> bool:
    """A bare entry reaches every backend; `{…, backends}` only those it names."""
    return isinstance(entry, str) or backend in (entry.get("backends") or [backend])
