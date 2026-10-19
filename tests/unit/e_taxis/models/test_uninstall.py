"""tests/unit/e_taxis/models/uninstall: an uninstall fails on its failed steps only."""

from e_taxis.models.catalog import Target
from e_taxis.models.uninstall import UninstallReport, UninstallStatus, UninstallStep


async def test_uninstall_report_failed_names_failed_steps() -> None:
    steps = tuple(UninstallStep(id=status.value, status=status, detail="") for status in UninstallStatus)
    assert UninstallReport(target=Target.CLAUDECODE, steps=steps).failed == ("failed",)
