"""codecs.markdown: a typeset document — placements in order, consecutive ones of one fragment forming a block.

`#h1` → `# text`, `#para` → the text, `#quote` → `> ` before every line, any other fragment → `## <fragment>` then
its parts. A block's parts are its non-empty values, stripped of surrounding newlines and joined by the block's
glue; a block with nothing in it is skipped. Blocks are joined by one blank line, with no trailing newline. A
document above the target's `limit` is refused whole: the harness would truncate it, so it never ships."""

import re
from itertools import groupby
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.models.error import RenderError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement

##### DEFAULTS #####
SEPARATOR: str = "\n\n"


##### UTILITIES #####
def block_markdown(fragment: str, parts: Sequence[str], glue: str) -> str:
    """One block's text from its non-empty parts."""
    body = glue.join(parts)
    match fragment:
        case "h1":
            return f"# {body}"
        case "para":
            return body
        case "quote":
            return "\n".join(f"> {line}" for line in body.split("\n"))
        case heading:
            return f"## {heading}{SEPARATOR}{body}"


def encode_markdown(path: str, target: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    blocks = [
        block_markdown(fragment, parts, members[0].glue)
        for fragment, group in groupby(placements, key=lambda placement: placement.fragment)
        for members in (list(group),)
        if (parts := [text for member in members if (text := str(member.value).strip("\n"))])
    ]
    text = SEPARATOR.join(blocks)
    match (limit := target.get("limit", 0)) and len(text) > limit:
        case True:
            msg = f"{path}: {len(text)} characters over the harness's limit of {limit}: refused, never truncated"
            raise RenderError(msg)
        case _:
            return text.encode()


def split_markdown(placements: Sequence[Placement]) -> dict[str, str]:
    """The rendered blocks by fragment — exactly the text each one encodes to."""
    return {
        fragment: block_markdown(fragment, parts, members[0].glue)
        for fragment, group in groupby(placements, key=lambda placement: placement.fragment)
        for members in (list(group),)
        if (parts := [text for member in members if (text := str(member.value).strip("\n"))])
    }


def read_markdown(text: str) -> dict[str, str]:
    """A live document's blocks by fragment: its preamble (`h1`, `quote`, `para`), then every `## heading` section."""
    preamble, *sections = re.split(r"(?m)^(?=## )", text)
    chunks = [chunk for chunk in preamble.strip("\n").split(SEPARATOR) if chunk.strip()]
    found = {
        "h1": "\n\n".join(chunk for chunk in chunks[:1] if chunk.startswith("# ")),
        "quote": SEPARATOR.join(chunk for chunk in chunks if chunk.startswith("> ")),
        "para": SEPARATOR.join(
            chunk
            for index, chunk in enumerate(chunks)
            if not chunk.startswith("> ") and not (index == 0 and chunk.startswith("# "))
        ),
    }
    heads = {section.split("\n", 1)[0][3:].strip(): section.rstrip("\n") for section in sections}
    return {**{key: value for key, value in found.items() if value}, **heads}
