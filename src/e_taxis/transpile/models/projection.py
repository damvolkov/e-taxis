"""models.projection: a core projected for one backend — every target's placements, and the bytes they encode to.

`placements` keeps declaration order per target: it is the provenance a plan, a report and a reverse read.
`files` are the encoded bytes of every file target, keyed by path relative to the tree; `registry` the entries a
registry target delivers (`mcp-user` → name → entry); `links` the symlinks a `link` target asks for."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from e_taxis.transpile.models.placement import Placement


##### TYPES #####
@dataclass(frozen=True, slots=True)
class Projection:
    backend: str
    out: str
    placements: Mapping[str, tuple[Placement, ...]]
    files: Mapping[str, bytes]
    registry: Mapping[str, Mapping[str, Any]]
    links: Mapping[str, str]
