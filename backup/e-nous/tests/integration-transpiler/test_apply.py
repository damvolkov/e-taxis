"""apply: core/ lands in the harness tree exactly as the spec places it."""

from __future__ import annotations

from ops.models.trial import Placement, Run


async def test_apply_lands(applied: Run) -> None:
    assert applied.ok, applied.stderr or applied.stdout[-2000:]


async def test_apply_places_every_file_and_link(placement: Placement) -> None:
    assert placement.ok, f"drift {placement.drift} · broken links {placement.links}"
