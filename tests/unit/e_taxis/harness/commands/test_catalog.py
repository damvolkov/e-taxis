"""tests/unit/e_taxis/commands/catalog: `map` and `doctor` as a user and a machine see them."""

import msgspec
import pytest


def test_catalog_map_lists_every_entry_with_its_rollouts(taxis, on_catalog) -> None:
    code, out, _ = taxis("map")
    assert code == 0
    assert all(part in out for part in ("alpha", "beta", "delta", "epsilon", "gamma", "house", "per-project"))


def test_catalog_map_json_filters_by_target(taxis, on_catalog) -> None:
    code, out, _ = taxis("map", "--target", "opencode", "--json")
    assert code == 0
    assert [entry["id"] for entry in msgspec.json.decode(out)] == ["alpha", "epsilon", "gamma"]


def test_catalog_map_on_a_broken_catalog_fails(taxis, on_doctor) -> None:
    code, _, err = taxis("map")
    assert code == 5
    assert "taxis doctor" in err


def test_catalog_doctor_sound_catalog_passes(taxis, on_catalog) -> None:
    code, out, _ = taxis("doctor")
    assert code == 0
    assert "5 entries, no problem" in out


@pytest.mark.parametrize("json", [False, True], ids=["table", "json"])
def test_catalog_doctor_broken_catalog_fails_with_every_problem(taxis, on_doctor, json: bool) -> None:
    code, out, err = taxis("doctor", *(["--json"] if json else []))
    assert code == 9
    assert "7 problem(s) in 3 entries" in err
    assert all(rule in out for rule in ("parse", "duplicate", "requires", "cycle", "primitive", "owns"))
