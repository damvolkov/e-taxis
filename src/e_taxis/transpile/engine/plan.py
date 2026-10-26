"""engine.plan: a projection held against the live tree — what landing it would change, fragment by fragment.

Ownership is total: a target is its render plus the parts its spec declares `foreign`, kept as they live (a Markdown
marker region, a structured key). Comparing per fragment, every finding names the row and the core paths behind it:
`missing` (the file is not there), `drift` (an owned fragment differs or is absent), `stale` (a live fragment, key
or governed file no row renders), `symlink` (an owned path is a link). The registry is compared entry by entry.
Pure: bytes and placements in, landed bytes and findings out."""

import re
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

from e_taxis.transpile.codecs.markdown import read_markdown, split_markdown
from e_taxis.transpile.codecs.matter import read_matter, split_matter
from e_taxis.transpile.codecs.structured import (
    MISSING,
    encode_json,
    get_structured,
    read_json,
    split_structured,
    strays_structured,
)
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.models.report import ReportFinding, ReportKind

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

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


def land_plan(
    fmt: str, rendered: bytes, live: bytes | None, foreign: Sequence[Mapping[str, Any]], placements: Sequence[Placement]
) -> bytes:
    """The bytes a target lands as: the render, its foreign parts carried over from the live file."""
    match (fmt, live):
        case (_, None) | (_, _) if not foreign:
            return rendered
        case ("md", bytes() as data):
            regions = regions_plan(data.decode(), foreign)
            return rendered + b"".join(
                region.encode() if region.startswith("\n") else SEPARATOR.encode() + region.encode()
                for region in regions
            )
        case ("json", bytes() as data):
            tree = read_json(data)
            owned = [placement.fragment for placement in placements]
            kept = [
                Placement("", stray, get_structured(tree, stray), "foreign", -1)
                for stray in strays_structured(tree, owned)
                if any(entry["kind"] == "key" and fnmatch(stray, entry["at"]) for entry in foreign)
            ]
            return encode_json("", {}, [*placements, *kept])
        case _:
            return rendered


def fragments_plan(
    fmt: str, placements: Sequence[Placement], data: bytes, foreign: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rendered and live fragments of one target, side by side; a format with no fragments compares whole."""
    match fmt:
        case "md":
            return split_markdown(placements), read_markdown(owned_plan(data.decode(), foreign))
        case "md+fm":
            wanted = [placement.fragment for placement in placements]
            return split_matter(placements), read_matter(data.decode(), wanted)
        case "json":
            tree = read_json(data)
            owned = [placement.fragment for placement in placements]
            strays = sorted(
                stray
                for stray in strays_structured(tree, owned)
                if not any(entry["kind"] == "key" and fnmatch(stray, entry["at"]) for entry in foreign)
            )
            live = {fragment: value for fragment in owned if (value := get_structured(tree, fragment)) is not MISSING}
            return split_structured(placements), {**live, **{stray: get_structured(tree, stray) for stray in strays}}
        case _:
            return {
                "": b"".join(
                    bytes(p.value) if isinstance(p.value, bytes) else str(p.value).encode() for p in placements
                )
            }, {"": data}


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
