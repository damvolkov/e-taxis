"""engine.plan: a projection held against the live tree — what landing it would change, fragment by fragment.

Ownership is total: a target is its render plus the parts its spec declares `foreign`, kept as they live (a Markdown
marker region, a structured key). Comparing per fragment, every finding names the row and the core paths behind it:
`missing` (the file is not there), `drift` (an owned fragment differs or is absent), `stale` (a live fragment, key
or governed file no row renders), `symlink` (an owned path is a link). The registry is compared entry by entry.
Pure: bytes and placements in, landed bytes and findings out."""

import re
from collections.abc import Mapping
from fnmatch import fnmatch
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.codecs.env import key_env, read_env
from e_taxis.transpile.codecs.markdown import read_markdown, split_markdown
from e_taxis.transpile.codecs.matter import read_matter, split_matter
from e_taxis.transpile.codecs.structured import (
    MISSING,
    encode_json,
    encode_toml,
    encode_yaml,
    get_structured,
    read_json,
    read_toml,
    read_yaml,
    split_structured,
    strays_structured,
)
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.models.report import ReportFinding, ReportKind

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

##### DEFAULTS #####
SEPARATOR: str = "\n\n"
STAR: str = "*"


##### UTILITIES #####
def regions_plan(text: str, foreign: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every live region a `marker` foreign entry declares, in the order they sit in the text."""
    spans = sorted(
        found.span()
        for entry in foreign
        if entry["kind"] == "marker"
        for found in re.finditer(rf"(?:{entry['start']})[\s\S]*?(?:{entry['end']})", text)
    )
    return [text[start:end] for start, end in spans]


def owned_plan(text: str, foreign: Sequence[Mapping[str, Any]]) -> str:
    """The live text without its foreign regions: what the render owns, as it is compared."""
    return re.sub(
        r"\n{3,}", SEPARATOR, "".join(re.split("|".join(map(re.escape, regions_plan(text, foreign))) or "(?!)", text))
    ).strip("\n")


def foreign_plan(foreign: Sequence[Mapping[str, Any]], kind: str) -> list[Mapping[str, Any]]:
    return [entry for entry in foreign if entry["kind"] == kind]


def dormant_plan(
    placements: Sequence[Placement], tree: Mapping[str, Any] | None, foreign: Sequence[Mapping[str, Any]]
) -> tuple[Placement, ...]:
    """The placements that land: none under a foreign table the live file does not hold (an export holds none)."""
    absent = [
        entry["at"]
        for entry in foreign_plan(foreign, "table")
        if tree is None or get_structured(tree, entry["at"]) is MISSING
    ]
    return tuple(
        placement
        for placement in placements
        if not any(placement.fragment == at or placement.fragment.startswith(f"{at}.") for at in absent)
    )


def items_plan(rendered: Any, live: Any, entry: Mapping[str, Any]) -> Any:
    """A shared list: ours by identity, each merged over its live twin (the harness's extra fields kept), then every
    live item the render does not name and `ours` does not claim — the harness's."""
    match (rendered, live):
        case (list(), list()):
            by, ours = entry["by"], entry.get("ours") or {}
            twins = {item.get(by): item for item in live if isinstance(item, Mapping)}
            named = {item.get(by) for item in rendered if isinstance(item, Mapping)}
            theirs = [
                item
                for item in live
                if isinstance(item, Mapping)
                and item.get(by) not in named
                and not (ours and all(item.get(k) == v for k, v in ours.items()))
            ]
            return [*({**twins.get(item.get(by), {}), **item} for item in rendered), *theirs]
        case _:
            return rendered


def carried_plan(
    placements: Sequence[Placement], tree: Mapping[str, Any], foreign: Sequence[Mapping[str, Any]]
) -> list[Placement]:
    """Our placements (shared lists merged), then every live key no row owns that a foreign key or table claims."""
    items = {entry["at"]: entry for entry in foreign_plan(foreign, "items")}
    merged = [
        Placement(
            p.target,
            p.fragment,
            items_plan(p.value, get_structured(tree, p.fragment), items[p.fragment]),
            p.section,
            p.row,
            p.sources,
            p.glue,
        )
        if p.fragment in items
        else p
        for p in placements
    ]
    claims = [entry["at"] for entry in foreign if entry["kind"] in ("key", "table")]
    kept = [
        Placement("", stray, get_structured(tree, stray), "foreign", -1)
        for stray in strays_structured(tree, [p.fragment for p in placements])
        if any(fnmatch(stray, at) or stray.startswith(f"{at}.") for at in claims)
    ]
    return [*merged, *kept]


def ours_plan(rendered: Any, live: Any, entry: Mapping[str, Any]) -> Any:
    """A live shared list as the render sees it: each of our items cut to the fields we render, then every unrendered
    item `ours` claims (stale); the harness's items are not ours to compare."""
    match (rendered, live):
        case (list(), list()):
            by, ours = entry["by"], entry.get("ours") or {}
            mine = {item.get(by): item for item in rendered if isinstance(item, Mapping)}
            twins = {item.get(by): item for item in live if isinstance(item, Mapping)}
            stale = [
                item
                for item in live
                if isinstance(item, Mapping)
                and item.get(by) not in mine
                and ours
                and all(item.get(k) == v for k, v in ours.items())
            ]
            return [
                *({key: twins[ident].get(key) for key in item} for ident, item in mine.items() if ident in twins),
                *stale,
            ]
        case _:
            return live


STRUCTURED: Final[Mapping[str, tuple[Callable[[bytes], dict[str, Any]], Callable[..., bytes]]]] = MappingProxyType(
    {"json": (read_json, encode_json), "toml": (read_toml, encode_toml), "yaml": (read_yaml, encode_yaml)}
)


def land_plan(
    fmt: str, rendered: bytes, live: bytes | None, foreign: Sequence[Mapping[str, Any]], placements: Sequence[Placement]
) -> bytes:
    """The bytes a target lands as: the render, its foreign parts carried over from the live file (none on export)."""
    match (fmt, live):
        case (_, _) if not foreign:
            return rendered
        case ("md", bytes() as data):
            regions = regions_plan(data.decode(), foreign)
            return rendered + b"".join(
                region.encode() if region.startswith("\n") else SEPARATOR.encode() + region.encode()
                for region in regions
            )
        case ("env", bytes() as data):
            owned = {placement.fragment for placement in placements}
            theirs = [
                line
                for line in data.decode().splitlines()
                if key_env(line) not in owned
                and any(fnmatch(key_env(line) or line, entry["at"]) for entry in foreign_plan(foreign, "key"))
            ]
            return rendered + "".join(f"{line}\n" for line in theirs).encode()
        case (str() as kind, _) if kind in STRUCTURED:
            read, encode = STRUCTURED[kind]
            tree = None if live is None else read(live)
            landing = dormant_plan(placements, tree, foreign)
            return encode("", {}, landing if tree is None else carried_plan(landing, tree, foreign))
        case _:
            return rendered


def rendered_plan(fmt: str, placements: Sequence[Placement]) -> dict[str, Any]:
    """The rendered fragments of one target, as `fragments_plan` compares them."""
    match fmt:
        case "md":
            return split_markdown(placements)
        case "md+fm":
            return split_matter(placements)
        case "json" | "toml" | "yaml":
            return split_structured(placements)
        case "env":
            return {placement.fragment: str(placement.value) for placement in placements}
        case _:
            return {
                "": b"".join(
                    bytes(p.value) if isinstance(p.value, bytes) else str(p.value).encode() for p in placements
                )
            }


def fragments_plan(
    fmt: str, placements: Sequence[Placement], data: bytes, foreign: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rendered and live fragments of one target, side by side; a format with no fragments compares whole."""
    match fmt:
        case "md":
            return rendered_plan(fmt, placements), read_markdown(owned_plan(data.decode(), foreign))
        case "md+fm":
            wanted = [placement.fragment for placement in placements]
            return rendered_plan(fmt, placements), read_matter(data.decode(), wanted)
        case "env":
            owned = {placement.fragment for placement in placements}
            claimed = [entry["at"] for entry in foreign_plan(foreign, "key")]
            live = {
                key: value
                for key, value in read_env(data).items()
                if key in owned or not any(fnmatch(key, at) for at in claimed)
            }
            return rendered_plan(fmt, placements), live
        case str() as kind if kind in STRUCTURED:
            tree = STRUCTURED[kind][0](data)
            placements = dormant_plan(placements, tree, foreign)
            owned = [placement.fragment for placement in placements]
            items = {entry["at"]: entry for entry in foreign_plan(foreign, "items")}
            claims = [entry["at"] for entry in foreign if entry["kind"] in ("key", "table")]
            strays = sorted(
                stray
                for stray in strays_structured(tree, owned)
                if not any(fnmatch(stray, at) or stray.startswith(f"{at}.") for at in claims)
            )
            live = {
                fragment: ours_plan(placement.value, value, items[fragment]) if fragment in items else value
                for placement in placements
                for fragment in (placement.fragment,)
                if (value := get_structured(tree, fragment)) is not MISSING
            }
            return rendered_plan(fmt, placements), {**live, **{stray: get_structured(tree, stray) for stray in strays}}
        case _:
            return rendered_plan(fmt, placements), {"": data}


def dormancy_plan(
    backend: str,
    path: str,
    fmt: str,
    placements: Sequence[Placement],
    *,
    live: bytes,
    foreign: Sequence[Mapping[str, Any]],
) -> Iterator[ReportFinding]:
    """Rows under a foreign table the live file does not hold: they wait, written once the harness creates it."""
    match fmt in STRUCTURED and bool(foreign_plan(foreign, "table")):
        case False:
            return
        case _:
            awake = {p.fragment for p in dormant_plan(placements, STRUCTURED[fmt][0](live), foreign)}
    yield from (
        ReportFinding(
            kind=ReportKind.DORMANT,
            backend=backend,
            where=p.origin,
            path=f"{path}#{p.fragment}",
            detail="under a table the harness has not created",
            sources=p.sources,
        )
        for p in placements
        if p.fragment not in awake
    )


def target_plan(
    backend: str,
    path: str,
    target: Mapping[str, Any],
    placements: Sequence[Placement],
    *,
    landed: bytes,
    live: bytes | None,
) -> Iterator[ReportFinding]:
    """The findings of one file target: missing, or each fragment that differs, is absent or is unowned."""
    first = placements[0]
    fmt = target.get("format", "file")
    match live:
        case None:
            yield ReportFinding(
                kind=ReportKind.MISSING, backend=backend, where=first.origin, path=path, sources=first.sources
            )
            return
        case _ if live == landed:
            return
        case _:
            pass
    rendered, found = fragments_plan(fmt, placements, live, target.get("foreign", []))
    yield from dormancy_plan(backend, path, fmt, placements, live=live, foreign=target.get("foreign", []))
    by = {placement.fragment: placement for placement in placements}
    drift = [
        ReportFinding(
            kind=ReportKind.DRIFT,
            backend=backend,
            where=by.get(fragment, first).origin,
            path=f"{path}#{fragment}" if fragment else path,
            sources=by.get(fragment, first).sources,
        )
        for fragment, value in rendered.items()
        if found.get(fragment, MISSING) != value
    ]
    stale = [
        ReportFinding(
            kind=ReportKind.STALE, backend=backend, where="—", path=f"{path}#{fragment}", detail="no row renders it"
        )
        for fragment in found
        if fragment not in rendered
    ]
    yield from drift
    yield from stale
    yield from (
        (
            ReportFinding(
                kind=ReportKind.DRIFT,
                backend=backend,
                where=first.origin,
                path=path,
                detail="same fragments, other bytes",
            ),
        )
        if not drift and not stale
        else ()
    )


def governed_plan(
    backend: str, govern: Sequence[str], foreign: Sequence[str], rendered: Sequence[str], live: Sequence[str]
) -> Iterator[ReportFinding]:
    """Live files inside a governed directory that no target renders and no foreign path covers."""
    yield from (
        ReportFinding(
            kind=ReportKind.STALE,
            backend=backend,
            where="govern",
            path=path,
            detail="in a governed directory, rendered by no row",
        )
        for path in sorted(set(live) - set(rendered))
        if any(path.startswith(f"{folder}/") for folder in govern)
        and not any(path == pattern or path.startswith(f"{pattern}/") or fnmatch(path, pattern) for pattern in foreign)
    )


def registry_plan(
    backend: str, name: str, placements: Sequence[Placement], live: Mapping[str, Any]
) -> Iterator[ReportFinding]:
    """Registry entries: one the render has and the harness lacks or holds otherwise, one the harness holds alone."""
    rendered = {placement.fragment: placement for placement in placements}
    yield from (
        ReportFinding(
            kind=ReportKind.MISSING if entry not in live else ReportKind.DRIFT,
            backend=backend,
            where=placement.origin,
            path=f"{name}#{entry}",
            sources=placement.sources,
        )
        for entry, placement in rendered.items()
        if live.get(entry) != placement.value
    )
    yield from (
        ReportFinding(
            kind=ReportKind.STALE,
            backend=backend,
            where="—",
            path=f"{name}#{entry}",
            detail="registered, rendered by no row",
        )
        for entry in live
        if entry not in rendered
    )
