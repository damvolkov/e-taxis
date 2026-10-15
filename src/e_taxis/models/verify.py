"""models.verify: each part's verify command, run — passed or not, and what it said."""

from msgspec import Struct

from e_taxis.models.catalog import Target


##### TYPES #####
class VerifyResult(Struct, frozen=True, kw_only=True):
    id: str
    passed: bool
    detail: str


class VerifyReport(Struct, frozen=True, kw_only=True):
    target: Target
    results: tuple[VerifyResult, ...] = ()

    @property
    def failed(self) -> tuple[VerifyResult, ...]:
        return tuple(result for result in self.results if not result.passed)
