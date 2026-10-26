"""codecs.structured: dotted fragments nested back into one document — JSON (indented), TOML, YAML; keys in row order."""

import tomllib
from collections.abc import Mapping
from functools import reduce
from typing import TYPE_CHECKING, Any

import eserde
import msgspec

if TYPE_CHECKING:
    from collections.abc import Sequence

    from e_taxis.transpile.models.placement import Placement

##### DEFAULTS #####
INDENT: int = 2
MISSING: object = object()


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


def split_structured(placements: Sequence[Placement]) -> dict[str, Any]:
    return {placement.fragment: placement.value for placement in placements}


def read_json(data: bytes) -> dict[str, Any]:
    """The live document as one tree, keys in file order. JSONC (comments) only when plain JSON fails: e-serde 0.5
    decodes JSONC into a map whose key order changes between processes, so its strays are sorted by the caller."""
    try:
        found = msgspec.json.decode(data)
    except msgspec.DecodeError:
        found = eserde.loads(data, format=eserde.Format.JSONC)
    return found if isinstance(found, dict) else {}


def get_structured(tree: Mapping[str, Any], fragment: str) -> Any:
    """The value at a dotted fragment, MISSING when any step is absent."""
    return reduce(
        lambda node, key: node.get(key, MISSING) if isinstance(node, Mapping) else MISSING, fragment.split("."), tree
    )


def strays_structured(tree: Mapping[str, Any], owned: Sequence[str], prefix: str = "") -> list[str]:
    """Every live key path no fragment owns: a path a fragment equals is owned whole; a path some fragment
    descends from is walked; any other is a stray."""
    return [
        stray
        for key, value in tree.items()
        for path in (f"{prefix}{key}",)
        if path not in owned
        for stray in (
            strays_structured(value, owned, f"{path}.")
            if isinstance(value, Mapping) and any(fragment.startswith(f"{path}.") for fragment in owned)
            else [path]
        )
    ]


def encode_toml(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    return eserde.dumps(nest_structured(placements), format=eserde.Format.TOML)


def encode_yaml(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    return eserde.dumps(nest_structured(placements), format=eserde.Format.YAML)


def read_toml(data: bytes) -> dict[str, Any]:
    found = tomllib.loads(data.decode()) if data.strip() else {}
    return dict(found)


def read_yaml(data: bytes) -> dict[str, Any]:
    found = eserde.loads(data, format=eserde.Format.YAML) if data.strip() else {}
    return found if isinstance(found, dict) else {}
