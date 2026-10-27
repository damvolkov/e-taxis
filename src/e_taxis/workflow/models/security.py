"""models.security: what a scanner reports and what the house accepted from it, as data.

`SecurityBaseline` is `core/<facet>/config/security.yaml`: per entity id, the findings a human read and accepted —
fingerprint (or the prefix a report prints) and file, each with its reason. The fingerprint hashes the matched text,
not its place, so an acceptance binds to one file: the same text elsewhere is a new finding."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from msgspec import Struct

from e_taxis.workflow.models.metrics import Finding

##### DEFAULTS #####
### severity rank, lowest first: a gate fails at or above its threshold.
SEVERITY: Final[Mapping[str, int]] = MappingProxyType({"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4})


##### TYPES #####
class Acceptance(Struct, frozen=True, forbid_unknown_fields=True):
    """One accepted finding: its fingerprint (or a prefix of it) in one file of the entity, and why."""

    fingerprint: str
    file: str
    why: str

    def covers(self, finding: Finding, root: str) -> bool:
        """Whether this silences `finding`, placed under the entity's core folder `root`."""
        return finding.fingerprint.startswith(self.fingerprint) and finding.path in {self.file, f"{root}/{self.file}"}


class SecurityBaseline(Struct, frozen=True, forbid_unknown_fields=True):
    """Entity id → its accepted findings."""

    accepted: dict[str, tuple[Acceptance, ...]] = {}


class ScanResult(Struct, frozen=True):
    """One scan as the scanner saw it: its name and pin, its risk score, its findings placed in the rendered tree."""

    scanner: str
    score: int
    findings: tuple[Finding, ...]
