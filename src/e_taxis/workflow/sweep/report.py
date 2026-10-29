"""sweep.report: the sweep as written — per voice how it read, the findings ranked, the commands that assess them.

`Report` is the answer (`radar/report.json`); `radar/report.md` is a view of it, rendered without a model. A finding fit
marked `new` and worth ASSESS or more ends with the exact command that assesses it, its primary link quoted for a
shell. `seen` is what the ledger records of this run, each URL under the voice it came through (the open web's
under `search`), dated the frame's last day: every entry read in the window, every link a finding cites."""

import shlex
from typing import TYPE_CHECKING

from e_taxis.workflow.models.sweep import SEARCH, FindingStatus, Report, VoiceRow

if TYPE_CHECKING:
    from e_taxis.workflow.models.sweep import Entries, Finding, Findings, Frame

##### DEFAULTS #####
ASSESS: int = 4
COMMAND: str = "taxis workflow run radar-tech"
PLANE: str = "the whole plane"


##### TYPES #####
class SweepReport:
    """Stateless: build the report, render it, say what the ledger keeps."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _build_assess(finding: Finding) -> str:
        return f"{COMMAND} {shlex.quote(f'tech={finding.links[0]}')}"

    @staticmethod
    def _render_voice(row: VoiceRow) -> str:
        status = f"{row.status}: {row.error}" if row.error else str(row.status)
        return f"| {row.id} | {status} | {row.parsed} · {row.in_window} · {row.new} | {row.findings} |"

    @classmethod
    def _render_finding(cls, rank: int, finding: Finding, assess: frozenset[str]) -> str:
        command = cls._build_assess(finding) if finding.links else ""
        lines = (
            f"### {rank}. {finding.title} — {finding.kind} · {finding.relevance}/5 · {finding.status or 'unfit'}",
            "",
            finding.description,
            "",
            f"**Why:** {finding.why}",
            "",
            *(f"- {fact}" for fact in finding.facts),
            "",
            f"Links: {' · '.join(finding.links)}",
            f"Sources: {' · '.join(finding.sources)}",
            *((f"Entities: {', '.join(finding.entities)}",) if finding.entities else ()),
            *((f"Incumbent: {finding.incumbent}",) if finding.incumbent else ()),
            f"Via: {finding.via} · {finding.published_at}",
            *(("", f"`{command}`") if command in assess else ()),
        )
        return "\n".join(lines)

    ############################################################

    ##### PUBLIC #####

    def build(self, entries: Entries, findings: Findings, path: str) -> Report:
        """The report of a run whose report.md lands at `path`."""
        vias = [finding.via for finding in findings.findings]
        return Report(
            path=path,
            voices=tuple(
                VoiceRow(
                    id=voice.id,
                    status=voice.status,
                    error=voice.error,
                    parsed=voice.parsed,
                    in_window=voice.in_window,
                    new=voice.new,
                    findings=vias.count(voice.id),
                )
                for voice in entries.voices
            ),
            findings=findings.findings,
            assess=tuple(
                self._build_assess(finding)
                for finding in findings.findings
                if finding.status is FindingStatus.NEW and finding.relevance >= ASSESS and finding.links
            ),
        )

    def render(self, frame: Frame, report: Report, notes: str) -> str:
        assess = frozenset(report.assess)
        body = (
            "\n\n".join(self._render_finding(rank, f, assess) for rank, f in enumerate(report.findings, 1))
            or "Nothing survived grounding."
        )
        lines = (
            f"# radar-field — {frame.topic or PLANE} · {frame.since} → {frame.until}",
            "",
            frame.brief,
            "",
            "## Voices",
            "",
            "| voice | status | parsed · in window · new | findings |",
            "|---|---|---|---|",
            *(self._render_voice(row) for row in report.voices),
            "",
            "## Findings",
            "",
            body,
            *(("", notes) if notes else ()),
        )
        return "\n".join(lines) + "\n"

    def seen(self, frame: Frame, entries: Entries, report: Report) -> dict[str, dict[str, str]]:
        read = {
            voice.id: {entry.url: frame.until for entry in voice.entries} for voice in entries.voices if voice.entries
        }
        cited: dict[str, dict[str, str]] = {}
        _ = [cited.setdefault(f.via or SEARCH, {}).update(dict.fromkeys(f.links, frame.until)) for f in report.findings]
        return {voice: read.get(voice, {}) | cited.get(voice, {}) for voice in read.keys() | cited.keys()}
