"""engine.encode: placements grouped per target and encoded by the target's format — the projection a run lands.

A concrete path finds its declared target by template (`skills/{id}/SKILL.md` matches `skills/x/SKILL.md`). A
placement no template declares is a file copied as it is: a reference beside its skill. A `registry` target
yields entries, never a file; a `link` target yields a symlink. Order is declaration order, per target."""

import re
from functools import reduce
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.codecs.catalog import ENCODERS
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.models.projection import Projection

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement

##### DEFAULTS #####
HOLE = re.compile(r"\\\{[^}]+\\\}")
FILE: str = "file"
REGISTRY: str = "registry"
LINK: str = "link"


##### UTILITIES #####
def match_target(path: str, targets: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    """The declared target a concrete path instantiates, or a plain file when none does."""
    found = [
        target for template, target in targets.items() if re.fullmatch(HOLE.sub(r"[^/]+", re.escape(template)), path)
    ]
    return found[0] if found else {"format": FILE}


def bind_encode(text: str, bindings: Mapping[str, str]) -> str:
    """A target template with its bindings (`{profile}`) filled."""
    return reduce(lambda acc, item: acc.replace(f"{{{item[0]}}}", item[1]), bindings.items(), text)


def encode_projection(
    backend: str,
    out: str,
    spec: Mapping[str, Any],
    placements: Sequence[Placement],
    bindings: Mapping[str, str] | None = None,
) -> Projection:
    order = list(dict.fromkeys(placement.target for placement in placements))
    grouped = {target: tuple(p for p in placements if p.target == target) for target in order}
    kinds = {path: match_target(path, spec["targets"]) for path in order}
    unknown = sorted({kind["format"] for kind in kinds.values()} - {*ENCODERS, REGISTRY, LINK})
    match unknown:
        case []:
            pass
        case _:
            msg = f"{backend}: no encoder yet for format(s) {', '.join(unknown)}"
            raise RenderError(msg)
    return Projection(
        backend=backend,
        out=out,
        placements=grouped,
        files={
            path: ENCODERS[kinds[path]["format"]](path, kinds[path], grouped[path])
            for path in order
            if kinds[path]["format"] not in (REGISTRY, LINK)
        },
        registry={
            path: {placement.fragment: placement.value for placement in grouped[path]}
            for path in order
            if kinds[path]["format"] == REGISTRY
        },
        links={
            bind_encode(template, bindings or {}): bind_encode(target["to"], bindings or {})
            for template, target in spec["targets"].items()
            if target.get("format") == LINK
        },
    )
