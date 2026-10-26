"""codecs.matter: Markdown with YAML frontmatter — the shape every instanced entity lands in.

`#fm.<key>` placements become the frontmatter in their order (empty values dropped, YAML as e-serde writes it);
`#title` is `# <value>` before the body, `#preload` a line before the body, `#body` the body itself."""

from typing import TYPE_CHECKING, Any

import eserde

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement

##### DEFAULTS #####
FRONT: str = "fm."
EMPTY: tuple[Any, ...] = (None, "", [], {})


##### UTILITIES #####
def encode_matter(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    front = {
        placement.fragment.removeprefix(FRONT): placement.value
        for placement in placements
        if placement.fragment.startswith(FRONT) and placement.value not in EMPTY
    }
    parts = {
        placement.fragment: str(placement.value) for placement in placements if not placement.fragment.startswith(FRONT)
    }
    yaml = eserde.dumps(front, format=eserde.Format.YAML).decode().rstrip()
    title = f"# {parts['title']}\n\n" if parts.get("title") else ""
    preload = f"{parts['preload']}\n\n" if parts.get("preload") else ""
    body = parts.get("body", "").rstrip()
    return f"---\n{yaml}\n---\n\n{title}{preload}{body}\n".encode()
