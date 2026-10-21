"""tests/unit/e_taxis/models/verify: a report fails on every result that did not pass."""

from e_taxis.harness.models.catalog import Target
from e_taxis.harness.models.verify import VerifyReport, VerifyResult


def test_verify_report_failed_holds_the_failures() -> None:
    results = (VerifyResult(id="a", passed=True, detail=""), VerifyResult(id="b", passed=False, detail="exit 1"))
    assert [result.id for result in VerifyReport(target=Target.OPENCODE, results=results).failed] == ["b"]
