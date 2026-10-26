"""engine.reverse: the live tree read back against the render and the last landing — who moved each fragment.

Three points per fragment: the render (core now), the live file (harness now), the base (a digest of what the last
landing wrote). Live equal to the render is settled. Live equal to the base means the core moved: `transpile run`
lands it. The render equal to the base means the harness moved: on a target that `absorb`s, a fragment one
invertible row owns is an absorb candidate, its value and core path named; anything else is held, and why. All
three apart: both moved. A fragment only the harness holds was added by it. With no landing recorded there is no
base: every difference is plain drift. Pure: digests compared, nothing written."""

import hashlib
from typing import TYPE_CHECKING, Any

import msgspec

from e_taxis.transpile.codecs.structured import MISSING
from e_taxis.transpile.engine.plan import fragments_plan
from e_taxis.transpile.models.report import ReportFinding, ReportKind

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement


##### UTILITIES #####
def digest_reverse(value: Any) -> str:
    """One fragment's digest: its bytes, or its canonical JSON."""
    return hashlib.sha256(value if isinstance(value, bytes) else msgspec.json.encode(value, order="sorted")).hexdigest()


def absorbable_reverse(spec: Mapping[str, Any], target: Mapping[str, Any], owners: Sequence[Placement]) -> str:
    """Why a harness edit can — or cannot — fold back into the core."""
    rows = [
        spec["map"][owner.section]["rows"][owner.row]
        for owner in owners
        if owner.section in spec["map"] and owner.row >= 0
    ]
    match (bool(target.get("absorb")), len(owners), [row.get("via") for row in rows if row.get("via")]):
        case (False, _, _):
            return "the target does not absorb: the next landing overwrites it"
        case (_, 0, _):
            return "added by the harness, no row renders it: it needs a home in the core"
        case (_, count, _) if count > 1:
            return f"held: one block of {count} slots ({', '.join(owner.sources[0] for owner in owners if owner.sources)}) — the edit is not split"
        case (_, _, [_, *_]):
            return "held: its row transforms the value, so it cannot be inverted"
        case _:
            return f"absorbable into `{', '.join(owners[0].sources)}`"


def classify_reverse(
    spec: Mapping[str, Any],
    path: str,
    target: Mapping[str, Any],
    placements: Sequence[Placement],
    *,
    live: bytes | None,
    base: Mapping[str, str] | None,
) -> Iterator[ReportFinding]:
    """Every fragment of one target that moved, with who moved it."""
    match live:
        case None:
            yield ReportFinding(
                kind=ReportKind.MISSING,
                backend=spec["backend"],
                where=placements[0].origin,
                path=path,
                detail="not in the live tree",
            )
            return
        case _:
            pass
    rendered, found = fragments_plan(target.get("format", "file"), placements, live, target.get("foreign", []))
    yield from (
        finding
        for fragment in sorted({*rendered, *found})
        if (
            finding := fragment_reverse(
                spec,
                path,
                target,
                placements,
                fragment,
                mine=rendered.get(fragment, MISSING),
                theirs=found.get(fragment, MISSING),
                base=base,
            )
        )
        is not None
    )


def fragment_reverse(
    spec: Mapping[str, Any],
    path: str,
    target: Mapping[str, Any],
    placements: Sequence[Placement],
    fragment: str,
    *,
    mine: Any,
    theirs: Any,
    base: Mapping[str, str] | None,
) -> ReportFinding | None:
    """One fragment's verdict, or None when the harness holds exactly what the core renders."""
    owners = [p for p in placements if p.fragment == fragment] or ([placements[0]] if not fragment else [])
    key = f"{path}#{fragment}" if fragment else path
    recorded = None if base is None else base.get(key)
    match (theirs == mine, base is None, recorded == digest_or_none(theirs), recorded == digest_or_none(mine)):
        case (True, _, _, _):
            return None
        case (_, True, _, _):
            kind, detail = ReportKind.DRIFT, "no landing recorded: no base to tell who moved"
        case (_, _, True, _):
            kind, detail = ReportKind.DRIFT, "the core moved: `transpile run --yes` lands it"
        case (_, _, _, True):
            kind, detail = ReportKind.HARNESS, f"the harness moved: {absorbable_reverse(spec, target, owners)}"
        case _:
            kind, detail = ReportKind.DRIFT, "both moved since the last landing: decide which wins"
    return ReportFinding(
        kind=kind,
        backend=spec["backend"],
        where=owners[0].origin if owners else "—",
        path=key,
        detail=detail,
        sources=tuple(source for owner in owners for source in owner.sources),
    )


def digest_or_none(value: Any) -> str | None:
    return None if value is MISSING else digest_reverse(value)
