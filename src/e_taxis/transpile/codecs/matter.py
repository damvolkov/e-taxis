"""codecs.matter: Markdown with YAML frontmatter — the shape every instanced entity lands in.

`#fm.<key>` placements become the frontmatter in their order (empty values dropped, YAML as e-serde writes it);
`#title` is `# <value>` before the body, `#preload` a line before the body, `#body` the body itself."""

import re
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


def split_matter(placements: Sequence[Placement]) -> dict[str, Any]:
    """The rendered fragments: each frontmatter key's value, and the title, preload line and body as written."""
    return {
        placement.fragment: placement.value if placement.fragment.startswith(FRONT) else str(placement.value).rstrip()
        for placement in placements
        if placement.value not in EMPTY
    }


def read_front(text: str) -> dict[str, Any]:
    """A live frontmatter's keys; an empty or unreadable one has none, so every owned key reads as drift."""
    try:
        found = eserde.loads(text, format=eserde.Format.YAML) if text.strip() else {}
    except eserde.LoadError:
        return {}
    return found if isinstance(found, dict) else {}


def read_matter(text: str, wanted: Sequence[str]) -> dict[str, Any]:
    """A live file's fragments: its frontmatter keys, then the title and preload line when the render has them."""
    match re.fullmatch(r"---\n(.*?)^---\n\n?(.*)", text, flags=re.DOTALL | re.MULTILINE):
        case None:
            return {"body": text.rstrip()}
        case found:
            front = read_front(found.group(1))
            rest = found.group(2)
    title, rest = (
        (rest[2:].split("\n", 1)[0], rest.split("\n", 1)[1].lstrip("\n"))
        if "title" in wanted and rest.startswith("# ") and "\n" in rest
        else ("", rest)
    )
    preload, rest = (
        (rest.split("\n\n", 1)[0], rest.split("\n\n", 1)[1]) if "preload" in wanted and "\n\n" in rest else ("", rest)
    )
    parts = {"title": title, "preload": preload, "body": rest.rstrip()}
    return {
        **{f"{FRONT}{key}": value for key, value in front.items()},
        **{key: value for key, value in parts.items() if value},
    }
