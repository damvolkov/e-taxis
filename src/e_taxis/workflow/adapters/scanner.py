"""adapters.scanner: SkillSpector over one rendered skill — static, zero tokens, pinned by the house stack.

The scanner runs through `uvx` from the install source the e-nous stack pins (`git+<link>@<pin>`); its JSON report is
decoded here into the house's `Finding`, still placed in the rendered tree (the node traces each one back to core/).
An issue without the scanner's fingerprint gets one from its rule and snippet; duplicates of one place are folded.
With an `llm` endpoint the LLM stage runs too (`skill/semantic`, weekly): its semantic analyzers and the meta-analyzer
that weeds out the static stage's false positives, on the house provider's OpenAI-compatible twin — never a vendor's
default. The key travels in the child's environment, never in the argv."""

import hashlib
from typing import TYPE_CHECKING

import msgspec

from e_taxis.workflow.models.error import ProviderError
from e_taxis.workflow.models.metrics import Finding
from e_taxis.workflow.models.security import ScanResult

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.models.endpoint import Endpoint
    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
NAME: str = "skillspector"


##### TYPES #####
class SpectorLocation(msgspec.Struct, frozen=True):
    file: str = ""
    start_line: int | None = None


class SpectorIssue(msgspec.Struct, frozen=True):
    id: str
    severity: str = "LOW"
    location: SpectorLocation | None = None
    finding: str | None = None
    pattern: str | None = None
    code_snippet: str | None = None
    match_fingerprint: str | None = None


class SpectorRisk(msgspec.Struct, frozen=True):
    score: int = 0


class SpectorReport(msgspec.Struct, frozen=True):
    risk_assessment: SpectorRisk = SpectorRisk()
    issues: tuple[SpectorIssue, ...] = ()


class SkillspectorScanner:
    """Satisfies ScannerPort over `uvx … skillspector scan [--no-llm] --format json`."""

    __slots__ = ("_command", "_limit")

    def __init__(self, command: CommandPort, limit: float) -> None:
        self._command = command
        self._limit = limit

    ##### PRIVATE METHODS #####

    @staticmethod
    def _scan_finding(issue: SpectorIssue) -> Finding:
        where = issue.location or SpectorLocation()
        stable = hashlib.sha256(f"{issue.id}\0{issue.code_snippet or ''}".encode()).hexdigest()
        return Finding(
            rule=issue.id,
            severity=issue.severity,
            path=where.file,
            line=where.start_line or 0,
            detail=" · ".join(part for part in (issue.pattern, issue.finding) if part),
            fingerprint=issue.match_fingerprint or stable,
        )

    @staticmethod
    def _scan_llm(llm: Endpoint) -> dict[str, str]:
        """The LLM stage pointed at the provider's OpenAI-compatible twin."""
        match llm.openai_url:
            case "":
                msg = f"the provider of {llm.model} declares no openai_url for SkillSpector's LLM stage"
                raise ProviderError(msg)
            case url:
                return {
                    "SKILLSPECTOR_PROVIDER": "openai_compatible",
                    "SKILLSPECTOR_COMPAT_BASE_URL": url,
                    "SKILLSPECTOR_COMPAT_API_KEY": llm.key,
                    "SKILLSPECTOR_MODEL": llm.model,
                }

    ############################################################

    ##### PUBLIC #####

    async def scan(self, folder: Path, source: str, llm: Endpoint | None = None) -> ScanResult:
        raw = await self._command.run(
            "uvx",
            "-q",
            "--from",
            source,
            NAME,
            "scan",
            str(folder),
            *(() if llm else ("--no-llm",)),
            "--format",
            "json",
            limit=self._limit,
            env=self._scan_llm(llm) if llm else None,
        )
        report = msgspec.json.decode(raw, type=SpectorReport)
        found = {(f.rule, f.path, f.line): f for f in map(self._scan_finding, report.issues)}
        return ScanResult(
            scanner=f"{NAME}@{source.rpartition('@')[2]}" + (f"+llm:{llm.model}" if llm else ""),
            score=report.risk_assessment.score,
            findings=tuple(found.values()),
        )
