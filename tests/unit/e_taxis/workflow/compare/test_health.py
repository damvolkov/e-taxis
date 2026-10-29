"""tests/unit/e_taxis/workflow/compare/health: each subject measured once, its hot path read from GitHub's languages."""

import datetime as dt
from typing import TYPE_CHECKING, Any

from e_taxis.workflow.assess.health import AssessHealth
from e_taxis.workflow.compare.health import CompareHealth

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from e_taxis.workflow.models.compare import Rivals
    from e_taxis.workflow.models.ports import ApiPort

GH = "https://api.github.com/repos"
NOW = dt.datetime(2026, 10, 29, tzinfo=dt.UTC)


async def test_health_measures_each_subject_once(stub: Callable[[Mapping[str, Any]], ApiPort], rivals: Rivals) -> None:
    api = stub(
        {
            f"{GH}/msgspec/msgspec/languages": {"Python": 60, "C": 40},
            f"{GH}/ijl/orjson/languages": {"Python": 90, "Rust": 10},
            f"{GH}/msgspec/msgspec": {"stargazers_count": 4190},
        }
    )
    found = await CompareHealth(api, AssessHealth(api)).measure(rivals, NOW)
    by = {vital.name: vital for vital in found.subjects}
    assert list(by) == ["msgspec", "orjson", "pydantic-core", "wreq"]
    assert (by["msgspec"].rust, by["msgspec"].stars) == (True, 4190)
    assert (by["orjson"].rust, by["orjson"].basis) == (
        False,
        ("Rust/C/C++ hold 10% of ijl/orjson's bytes (GitHub /languages)",),
    )
    assert by["pydantic-core"].basis == ("no language breakdown for pydantic/pydantic-core",)
    assert (by["wreq"].rust, by["wreq"].stars, by["wreq"].basis) == (
        False,
        None,
        ("no language breakdown for a subject without a repository",),
    )
    assert found.measured_at == NOW.isoformat()
