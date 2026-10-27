"""tests/unit/e_taxis/workflow/commands/reports: `taxis reports show` rebuilds a plane run's report from its ledger."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.services.plane import PlaneRun

type Taxis = Callable[..., tuple[int, str, str]]


def test_reports_show_latest_markdown(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    taxis("eval", "run", "agent", "--nous", str(plane_nous), "--cadence", "commit")
    code, out, _ = taxis("reports", "show", "--nous", str(plane_nous))
    assert code == 0
    assert out.startswith("# evaluator agent · ")
    assert "## builder" in out


def test_reports_show_json(taxis: Taxis, plane_nous: Path, plane_deps: PlaneRun) -> None:
    taxis("eval", "run", "agent", "--nous", str(plane_nous), "--cadence", "commit")
    code, out, _ = taxis("reports", "show", "latest", "--nous", str(plane_nous), "--json")
    assert code == 0
    assert json.loads(out)["manifest"]["target"] == "agent"
