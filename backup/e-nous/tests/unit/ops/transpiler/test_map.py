"""Unit tests for the persona equivalence map: determinism, facet areas, and the slot placements the specs declare."""

from __future__ import annotations

from pathlib import Path

import pytest

from ops.core.settings import settings
from ops.models.entity import BACKENDS, Harness
from ops.transpiler.map import PersonaMap
from ops.transpiler.render import Transpiler


@pytest.fixture
def persona_map() -> PersonaMap:
    """The map over the real corpus: it reads core/ and specs/, it writes nowhere."""
    return PersonaMap()


def test_map_deterministic_across_instances(persona_map: PersonaMap) -> None:
    """Two renders of the same corpus are identical, in every projection."""
    again = PersonaMap()
    assert persona_map.text() == again.text()
    assert persona_map.markdown() == again.markdown()
    assert all(persona_map.grid(h) == again.grid(h) for h in Harness)


def test_map_areas_carry_own_facet(persona_map: PersonaMap) -> None:
    """The tekton area shows only base + tekton sources; the nomos area only base + nomos."""
    tekton, nomos = persona_map.text().split("NOMOS")
    assert "core/tekton/persona/" in tekton and "core/nomos" not in tekton
    assert "core/nomos/persona/" in nomos and "core/tekton" not in nomos


def test_map_face_equivalence_per_harness(persona_map: PersonaMap) -> None:
    """One slot name, two sources: face follows the facet of its harness into the document each spec picks."""
    tekton_row = next(row for row in persona_map.grid(Harness.TEKTON)[1:] if row[1] == "face")
    assert tekton_row[0] == "core/tekton/persona/character/face.md"
    assert all("AGENTS.md · The engineer" in cell or "CLAUDE.md · The engineer" in cell for cell in tekton_row[2:])
    nomos_row = next(row for row in persona_map.grid(Harness.NOMOS)[1:] if row[1] == "face")
    assert nomos_row[0] == "core/nomos/persona/character/face.md"
    assert "SOUL.md · Personality" in nomos_row[2] and "SOUL.md · Personality" in nomos_row[3]


@pytest.mark.parametrize("harness", list(Harness))
def test_map_places_every_spec_slot(persona_map: PersonaMap, harness: Harness, tmp_path: Path) -> None:
    """Every slot any backend of the harness names in its persona spec holds a cell in its column."""
    grid = persona_map.grid(harness)
    placed = {row[1] for row in grid[1:]}
    for index, backend in enumerate(BACKENDS[harness], start=2):
        reader = Transpiler(settings.ROOT, backend, tmp_path / backend.value)
        for doc in reader.documents:
            for block in doc.blocks:
                missing = [slot for slot in block.slots if slot not in placed]
                assert not missing, f"{backend.value}: slots with no row: {missing}"
                assert all(row[index] != "—" for row in grid[1:] if row[1] in block.slots)
