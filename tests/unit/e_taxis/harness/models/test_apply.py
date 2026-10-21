"""tests/unit/e_taxis/models/apply: an apply fails on a failed step or a failed verify, never on a skip or a deferral."""

from e_taxis.harness.models.apply import ApplyReport, ApplyStatus, ApplyStep
from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.verify import VerifyResult


async def test_apply_report_failed_names_failed_steps_and_verifies() -> None:
    steps = tuple(ApplyStep(id=status.value, status=status, detail="") for status in ApplyStatus)
    verify = (VerifyResult(id="applied", passed=False, detail="exit 1"), VerifyResult(id="x", passed=True, detail=""))
    report = ApplyReport(target=Target.CLAUDECODE, steps=steps, verify=verify)
    assert report.failed == ("failed", "applied")
