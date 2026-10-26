"""codecs.structured: dotted fragments nested back into one document — JSON today, indented, keys in row order."""

from functools import reduce
from typing import TYPE_CHECKING, Any

import eserde
import msgspec

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement

##### DEFAULTS #####
INDENT: int = 2


##### UTILITIES #####
def put_structured(tree: dict[str, Any], placement: Placement) -> dict[str, Any]:
    """One placement set at its dotted fragment, its parent tables created on the way."""
    *parents, leaf = placement.fragment.split(".")
    reduce(lambda acc, key: acc.setdefault(key, {}), parents, tree)[leaf] = placement.value
    return tree


def nest_structured(placements: Sequence[Placement]) -> dict[str, Any]:
    """`a.b.c` fragments as nested tables, first appearance fixing each key's place."""
    return reduce(put_structured, placements, {})


def encode_json(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    raw = eserde.dumps(nest_structured(placements), format=eserde.Format.JSON)
    return msgspec.json.format(raw, indent=INDENT) + b"\n"
