"""tests/unit/e_taxis/services/verify: every resolved part's verify, run — an unknown part cannot pass."""

from typing import TYPE_CHECKING

from e_taxis.models.catalog import Target

if TYPE_CHECKING:
    from e_taxis.services.verify import VerifyService


async def test_verify_run(verifier: VerifyService, house) -> None:
    report = await verifier.run(house, Target.CLAUDECODE)
    assert [(result.id, result.passed) for result in report.results] == [
        ("alpha", True),
        ("delta", True),
        ("beta", False),
        ("ghost", False),
    ]
    assert report.results[-1].detail == "no catalog entry · wanted by profile:house"
